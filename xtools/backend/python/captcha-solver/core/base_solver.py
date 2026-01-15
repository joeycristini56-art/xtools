from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from models.base import CaptchaType
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseSolver(ABC):
    """Abstract base class for all CAPTCHA solvers."""
    
    def __init__(self, solver_name: str, captcha_type: CaptchaType):
        self.solver_name = solver_name
        self.captcha_type = captcha_type
        self.is_initialized = False
    
    async def initialize(self) -> None:
        """Initialize the solver (load models, setup resources, etc.)."""
        if not self.is_initialized:
            await self._initialize()
            self.is_initialized = True
            logger.info(f"Solver {self.solver_name} initialized")
    
    @abstractmethod
    async def _initialize(self) -> None:
        """Solver-specific initialization logic."""
        pass
    
    @abstractmethod
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[Any]:
        """
        Solve the CAPTCHA.
        
        Args:
            captcha_data: Dictionary containing CAPTCHA data and parameters
            
        Returns:
            Solution data or None if solving failed
        """
        pass
    
    async def cleanup(self) -> None:
        """Clean up solver resources."""
        if self.is_initialized:
            await self._cleanup()
            self.is_initialized = False
            logger.info(f"Solver {self.solver_name} cleaned up")
    
    async def _cleanup(self) -> None:
        """Solver-specific cleanup logic."""
        pass
    
    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """
        Validate input data for the solver.
        
        Args:
            captcha_data: Dictionary containing CAPTCHA data
            
        Returns:
            True if input is valid, False otherwise
        """
        return True
    
    async def preprocess_data(self, captcha_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess CAPTCHA data before solving.
        
        Args:
            captcha_data: Raw CAPTCHA data
            
        Returns:
            Preprocessed CAPTCHA data
        """
        return captcha_data
    
    async def postprocess_result(self, result: Any, captcha_data: Dict[str, Any]) -> Any:
        """
        Postprocess solver result.
        
        Args:
            result: Raw solver result
            captcha_data: Original CAPTCHA data
            
        Returns:
            Processed result
        """
        return result
    
    def get_solver_info(self) -> Dict[str, Any]:
        """Get information about the solver."""
        return {
            'name': self.solver_name,
            'captcha_type': self.captcha_type,
            'initialized': self.is_initialized,
            'description': self.__doc__ or f"Solver for {self.captcha_type} CAPTCHAs"
        }
    
    async def test_solver(self, test_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Test if the solver is working correctly.
        
        Args:
            test_data: Optional test data
            
        Returns:
            True if solver is working, False otherwise
        """
        try:
            if not self.is_initialized:
                await self.initialize()
            
            if not test_data:
                return self.is_initialized
            
            result = await self.solve(test_data)
            return result is not None
            
        except Exception as e:
            logger.error(f"Solver {self.solver_name} test failed: {e}")
            return False
    
    def __str__(self) -> str:
        return f"{self.solver_name} ({self.captcha_type})"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.solver_name}>"