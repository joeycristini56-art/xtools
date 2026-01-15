import re
import cv2
import numpy as np
import easyocr
from typing import Any, Dict, Optional, Union
from core.base_solver import BaseSolver
from models.base import CaptchaType
from models.responses import MathSolution
from utils.advanced_image_utils import AdvancedImageProcessor
from utils.logger import get_logger
from utils.cache_utils import cache_manager

logger = get_logger(__name__)


class MathSolver(BaseSolver):
    """Advanced math CAPTCHA solver supporting both text and image-based math problems."""
    
    def __init__(self):
        super().__init__("MathSolver", CaptchaType.MATH_CAPTCHA)
        self.ocr_reader = None
        self.image_processor = AdvancedImageProcessor()
    
    async def _initialize(self) -> None:
        """Initialize math solver with OCR capabilities."""
        try:
            self.ocr_reader = easyocr.Reader(['en'], gpu=False)
            logger.info("Math solver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize math solver: {e}")
            raise
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[MathSolution]:
        """
        Solve math CAPTCHA supporting both text and image inputs.
        
        Args:
            captcha_data: Dictionary containing:
                - expression: Math expression to solve (text)
                - image_data: Base64 encoded image with math expression
                - question: Optional question text
                - math_expression: Alternative field for math expression
        
        Returns:
            MathSolution with answer or None if failed
        """
        try:
            if not self.validate_input(captcha_data):
                return None
            
            expression = None
            cache_key = ""
            
            if captcha_data.get('expression') or captcha_data.get('math_expression'):
                expression = captcha_data.get('expression') or captcha_data.get('math_expression')
                cache_key = f"text_{expression}"
            
            elif captcha_data.get('question'):
                expression = captcha_data.get('question')
                cache_key = f"text_{expression}"
            
            elif captcha_data.get('image_data'):
                image_data = captcha_data.get('image_data')
                cache_key = f"image_{image_data[:50]}"
                
                cached_result = await cache_manager.get_cached_model_result("math", cache_key)
                if cached_result:
                    logger.debug("Using cached math result")
                    return MathSolution(**cached_result)
                
                expression = await self._extract_expression_from_image(image_data)
                if not expression:
                    logger.warning("Could not extract math expression from image")
                    return None
            
            if not expression:
                logger.warning("No math expression found")
                return None
            
            if not captcha_data.get('image_data'):
                cached_result = await cache_manager.get_cached_model_result("math", cache_key)
                if cached_result:
                    logger.debug("Using cached math result")
                    return MathSolution(**cached_result)
            
            cleaned_expressions = await self._extract_all_expressions(expression)
            
            if not cleaned_expressions:
                logger.warning("Could not extract valid math expressions")
                return None
            
            for cleaned_expression in cleaned_expressions:
                answer = await self._evaluate_expression_safely(cleaned_expression)
                
                if answer is not None:
                    solution = MathSolution(
                        answer=answer,
                        expression=cleaned_expression,
                        confidence=0.95
                    )
                    
                    await cache_manager.cache_model_result("math", cache_key, solution.dict())
                    
                    logger.info(f"Math CAPTCHA solved: {cleaned_expression} = {answer}")
                    return solution
            
            logger.warning("Could not solve any extracted math expressions")
            return None
            
        except Exception as e:
            logger.error(f"Error solving math CAPTCHA: {e}")
            return None
    
    async def _extract_expression_from_image(self, image_data: str) -> Optional[str]:
        """Extract math expression from image using OCR."""
        try:
            image = self.image_processor.decode_base64_image(image_data)
            
            processed_image = await self._preprocess_math_image(image)
            
            results = self.ocr_reader.readtext(processed_image)
            
            extracted_text = " ".join([result[1] for result in results if result[2] > 0.5])
            
            logger.debug(f"OCR extracted text: {extracted_text}")
            return extracted_text
            
        except Exception as e:
            logger.error(f"Error extracting expression from image: {e}")
            return None
    
    async def _preprocess_math_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better math OCR."""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image.copy()
            
            enhanced = self.image_processor.enhance_image_quality(gray)
            
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            kernel = np.ones((2, 2), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
            
            height, width = cleaned.shape
            if height < 50:
                scale_factor = 50 / height
                new_width = int(width * scale_factor)
                cleaned = cv2.resize(cleaned, (new_width, 50), interpolation=cv2.INTER_CUBIC)
            
            return cleaned
            
        except Exception as e:
            logger.debug(f"Error preprocessing math image: {e}")
            return image
    
    async def _extract_all_expressions(self, text: str) -> list[str]:
        """Extract all possible math expressions from text."""
        expressions = []
        
        cleaned = self._clean_expression(text)
        if cleaned:
            expressions.append(cleaned)
        
        advanced_expressions = await self._advanced_expression_extraction(text)
        expressions.extend(advanced_expressions)
        
        word_expressions = await self._convert_words_to_numbers(text)
        expressions.extend(word_expressions)
        
        unique_expressions = []
        for expr in expressions:
            if expr not in unique_expressions:
                unique_expressions.append(expr)
        
        return unique_expressions
    
    async def _advanced_expression_extraction(self, text: str) -> list[str]:
        """Advanced extraction of math expressions."""
        expressions = []
        text = text.lower().strip()
        
        complex_pattern = r'(\(?\d+(?:\.\d+)?\)?)\s*([+\-*/])\s*(\(?\d+(?:\.\d+)?\)?)'
        matches = re.findall(complex_pattern, text)
        for match in matches:
            expr = f"{match[0]} {match[1]} {match[2]}"
            expressions.append(expr.replace('(', '').replace(')', ''))
        
        multi_pattern = r'(\d+(?:\.\d+)?(?:\s*[+\-*/]\s*\d+(?:\.\d+)?)+)'
        multi_matches = re.findall(multi_pattern, text)
        expressions.extend(multi_matches)
        
        fraction_pattern = r'(\d+(?:\.\d+)?)\s*(?:divided by|/)\s*(\d+(?:\.\d+)?)'
        fraction_matches = re.findall(fraction_pattern, text)
        for match in fraction_matches:
            expressions.append(f"{match[0]} / {match[1]}")
        
        power_pattern = r'(\d+(?:\.\d+)?)\s*(?:to the power of|raised to|\^|\*\*)\s*(\d+(?:\.\d+)?)'
        power_matches = re.findall(power_pattern, text)
        for match in power_matches:
            expressions.append(f"{match[0]} ** {match[1]}")
        
        return expressions
    
    async def _convert_words_to_numbers(self, text: str) -> list[str]:
        """Convert word-based math expressions to numeric expressions."""
        expressions = []
        text = text.lower()
        
        word_to_num = {
            'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
            'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
            'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
            'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
            'eighteen': '18', 'nineteen': '19', 'twenty': '20'
        }
        
        text = re.sub(r'\bplus\b', '+', text)
        text = re.sub(r'\bminus\b', '-', text)
        text = re.sub(r'\btimes\b', '*', text)
        text = re.sub(r'\bmultiplied by\b', '*', text)
        text = re.sub(r'\bdivided by\b', '/', text)
        
        for word, num in word_to_num.items():
            text = re.sub(rf'\b{word}\b', num, text)
        
        pattern = r'(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)'
        matches = re.findall(pattern, text)
        for match in matches:
            expressions.append(f"{match[0]} {match[1]} {match[2]}")
        
        return expressions
    
    async def _evaluate_expression_safely(self, expression: str) -> Optional[Union[int, float]]:
        """Safely evaluate mathematical expression with enhanced security."""
        try:
            expression = expression.strip()
            
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in expression):
                logger.warning(f"Expression contains unsafe characters: {expression}")
                return None
            
            dangerous_patterns = ['__', 'import', 'exec', 'eval', 'open', 'file']
            if any(pattern in expression.lower() for pattern in dangerous_patterns):
                logger.warning(f"Expression contains dangerous patterns: {expression}")
                return None
            
            if len(expression) > 100:
                logger.warning(f"Expression too long: {expression}")
                return None
            
            result = None
            
            try:
                result = eval(expression)
            except:
                pass
            
            if result is None:
                result = await self._manual_expression_evaluation(expression)
            
            if result is None:
                result = await self._ast_evaluation(expression)
            
            if result is not None:
                if isinstance(result, float) and result.is_integer():
                    return int(result)
                return result
            
            return None
            
        except Exception as e:
            logger.debug(f"Error evaluating expression '{expression}': {e}")
            return None
    
    async def _manual_expression_evaluation(self, expression: str) -> Optional[Union[int, float]]:
        """Manually evaluate simple math expressions."""
        try:
            pattern = r'^\s*(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)\s*$'
            match = re.match(pattern, expression)
            
            if match:
                num1, operator, num2 = match.groups()
                num1, num2 = float(num1), float(num2)
                
                if operator == '+':
                    return num1 + num2
                elif operator == '-':
                    return num1 - num2
                elif operator == '*':
                    return num1 * num2
                elif operator == '/':
                    if num2 != 0:
                        return num1 / num2
                    else:
                        logger.warning("Division by zero")
                        return None
            
            return None
            
        except Exception as e:
            logger.debug(f"Manual evaluation failed: {e}")
            return None
    
    async def _ast_evaluation(self, expression: str) -> Optional[Union[int, float]]:
        """Evaluate expression using AST for enhanced security."""
        try:
            import ast
            import operator
            
            ops = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
                ast.USub: operator.neg,
            }
            
            def eval_node(node):
                if isinstance(node, ast.Num):
                    return node.n
                elif isinstance(node, ast.Constant):
                    return node.value
                elif isinstance(node, ast.BinOp):
                    left = eval_node(node.left)
                    right = eval_node(node.right)
                    return ops[type(node.op)](left, right)
                elif isinstance(node, ast.UnaryOp):
                    operand = eval_node(node.operand)
                    return ops[type(node.op)](operand)
                else:
                    raise TypeError(f"Unsupported node type: {type(node)}")
            
            tree = ast.parse(expression, mode='eval')
            return eval_node(tree.body)
            
        except Exception as e:
            logger.debug(f"AST evaluation failed: {e}")
            return None
    
    def _clean_expression(self, text: str) -> Optional[str]:
        """Clean and extract math expression from text."""
        text = text.lower().strip()
        text = re.sub(r'^(what is|solve|calculate|find|answer)', '', text)
        text = re.sub(r'[?=].*$', '', text)
        text = text.strip()
        
        text = re.sub(r'\bplus\b', '+', text)
        text = re.sub(r'\bminus\b', '-', text)
        text = re.sub(r'\btimes\b', '*', text)
        text = re.sub(r'\bmultiplied by\b', '*', text)
        text = re.sub(r'\bdivided by\b', '/', text)
        text = re.sub(r'\bx\b', '*', text)
        
        pattern = r'(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)'
        match = re.search(pattern, text)
        
        if match:
            num1, operator, num2 = match.groups()
            return f"{num1} {operator} {num2}"
        
        numbers = re.findall(r'\d+(?:\.\d+)?', text)
        operators = re.findall(r'[+\-*/]', text)
        
        if len(numbers) >= 2 and len(operators) >= 1:
            return f"{numbers[0]} {operators[0]} {numbers[1]}"
        
        return None
    
    def _evaluate_expression(self, expression: str) -> Optional[float]:
        """Safely evaluate mathematical expression."""
        try:
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in expression):
                logger.warning(f"Expression contains unsafe characters: {expression}")
                return None
            
            result = eval(expression)
            
            if isinstance(result, float) and result.is_integer():
                return int(result)
            
            return result
            
        except Exception as e:
            logger.debug(f"Error evaluating expression '{expression}': {e}")
            return None
    
    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """Validate input data for math CAPTCHA solving."""
        expression = captcha_data.get('expression')
        math_expression = captcha_data.get('math_expression')
        question = captcha_data.get('question')
        image_data = captcha_data.get('image_data')
        
        if not expression and not math_expression and not question and not image_data:
            logger.error("No expression, math_expression, question, or image_data provided")
            return False
        
        return True
    
    async def _cleanup(self) -> None:
        """Clean up math solver resources."""
        self.ocr_reader = None
        logger.debug("Math solver resources cleaned up")