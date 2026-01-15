from typing import Dict, Optional, Type, List
from models.base import CaptchaType
from utils.logger import get_logger
from .base_solver import BaseSolver

logger = get_logger(__name__)


class SolverFactory:
    """Factory for creating and managing CAPTCHA solvers."""

    def __init__(self):
        self._solvers: Dict[CaptchaType, Type[BaseSolver]] = {}
        self._solver_instances: Dict[CaptchaType, BaseSolver] = {}
        self._initialized = False

    def register_solver(self, captcha_type: CaptchaType, solver_class: Type[BaseSolver]) -> None:
        """Register a solver class for a specific CAPTCHA type."""
        self._solvers[captcha_type] = solver_class
        logger.info(f"Registered solver {solver_class.__name__} for {captcha_type}")

    async def initialize_all_solvers(self) -> None:
        """Initialize all registered solvers."""
        if self._initialized:
            return

        logger.info("Initializing all CAPTCHA solvers")

        for captcha_type, solver_class in self._solvers.items():
            try:
                solver_instance = solver_class()

                await solver_instance.initialize()

                self._solver_instances[captcha_type] = solver_instance

                logger.info(f"Successfully initialized {solver_class.__name__} for {captcha_type}")

            except Exception as e:
                logger.error(f"Failed to initialize solver for {captcha_type}: {e}")

        self._initialized = True
        logger.info(f"Solver factory initialized with {len(self._solver_instances)} solvers")

    def get_solver(self, captcha_type: str) -> Optional[BaseSolver]:
        """Get a solver instance for the specified CAPTCHA type."""
        try:
            if isinstance(captcha_type, str):
                captcha_type = CaptchaType(captcha_type.lower())

            return self._solver_instances.get(captcha_type)

        except ValueError:
            logger.error(f"Unknown CAPTCHA type: {captcha_type}")
            return None

    def get_available_solvers(self) -> List[str]:
        """Get list of available CAPTCHA types."""
        return [captcha_type.value for captcha_type in self._solver_instances.keys()]

    def get_solver_info(self, captcha_type: str) -> Optional[Dict]:
        """Get information about a specific solver."""
        solver = self.get_solver(captcha_type)
        if solver:
            return solver.get_solver_info()
        return None

    def get_all_solver_info(self) -> Dict[str, Dict]:
        """Get information about all solvers."""
        return {
            captcha_type.value: solver.get_solver_info()
            for captcha_type, solver in self._solver_instances.items()
        }

    async def test_solver(self, captcha_type: str, test_data: Optional[Dict] = None) -> bool:
        """Test a specific solver."""
        solver = self.get_solver(captcha_type)
        if solver:
            return await solver.test_solver(test_data)
        return False

    async def test_all_solvers(self) -> Dict[str, bool]:
        """Test all solvers."""
        results = {}
        for captcha_type, solver in self._solver_instances.items():
            try:
                results[captcha_type.value] = await solver.test_solver()
            except Exception as e:
                logger.error(f"Error testing solver {captcha_type}: {e}")
                results[captcha_type.value] = False

        return results

    async def cleanup_all_solvers(self) -> None:
        """Clean up all solver instances."""
        logger.info("Cleaning up all solvers")

        for captcha_type, solver in self._solver_instances.items():
            try:
                await solver.cleanup()
                logger.debug(f"Cleaned up solver for {captcha_type}")
            except Exception as e:
                logger.error(f"Error cleaning up solver for {captcha_type}: {e}")

        self._solver_instances.clear()
        self._initialized = False
        logger.info("All solvers cleaned up")

    def is_solver_available(self, captcha_type: str) -> bool:
        """Check if a solver is available for the given CAPTCHA type."""
        try:
            if isinstance(captcha_type, str):
                captcha_type = CaptchaType(captcha_type.lower())
            return captcha_type in self._solver_instances
        except ValueError:
            return False

    def get_solver_stats(self) -> Dict[str, any]:
        """Get statistics about registered solvers."""
        available_solvers = self.get_available_solvers()
        return {
            'total': len(self._solvers),
            'available': len(self._solver_instances),
            'solvers': available_solvers,
            'initialization_status': self._initialized,
            'total_registered': len(self._solvers),
            'total_initialized': len(self._solver_instances),
            'available_types': available_solvers
        }


solver_factory = SolverFactory()


async def register_all_solvers():
    """Register all available enhanced solvers."""
    try:
        from solvers.slider.advanced_slider_solver import AdvancedSliderSolver
        solver_factory.register_solver(CaptchaType.SLIDER_CAPTCHA, AdvancedSliderSolver)

        from solvers.text.text_solver import AdvancedTextSolver
        solver_factory.register_solver(CaptchaType.TEXT, AdvancedTextSolver)

        from solvers.image.advanced_image_grid_solver import AdvancedImageGridSolver
        solver_factory.register_solver(CaptchaType.IMAGE_GRID, AdvancedImageGridSolver)

        from solvers.audio.audio_solver import AdvancedAudioSolver
        solver_factory.register_solver(CaptchaType.AUDIO, AdvancedAudioSolver)

        from solvers.recaptcha.recaptcha_v2_solver import RecaptchaV2Solver
        from solvers.recaptcha.recaptcha_v3_solver import RecaptchaV3Solver
        solver_factory.register_solver(CaptchaType.RECAPTCHA_V2, RecaptchaV2Solver)
        solver_factory.register_solver(CaptchaType.RECAPTCHA_V3, RecaptchaV3Solver)

        from solvers.turnstile.turnstile_solver import TurnstileSolver
        solver_factory.register_solver(CaptchaType.TURNSTILE, TurnstileSolver)

        from solvers.arkose.arkose_solver import ArkoseSolver
        solver_factory.register_solver(CaptchaType.ARKOSE, ArkoseSolver)
        solver_factory.register_solver(CaptchaType.FUNCAPTCHA, ArkoseSolver)

        from solvers.rotation.rotation_solver import AdvancedRotationSolver
        solver_factory.register_solver(CaptchaType.IMAGE_ROTATION, AdvancedRotationSolver)

        from solvers.dice.dice_solver import AdvancedDiceSolver
        solver_factory.register_solver(CaptchaType.DICE_SELECTION, AdvancedDiceSolver)

        from solvers.dice.math_solver import MathSolver
        solver_factory.register_solver(CaptchaType.MATH_CAPTCHA, MathSolver)

        from solvers.image.object_identification_solver import ObjectIdentificationSolver
        solver_factory.register_solver(CaptchaType.OBJECT_IDENTIFICATION, ObjectIdentificationSolver)

        from solvers.datadome.datadome_solver import DataDomeSolver
        solver_factory.register_solver(CaptchaType.DATADOME, DataDomeSolver)

        logger.info("All enhanced solvers registered successfully")

    except ImportError as e:
        logger.error(f"Failed to import enhanced solver: {e}")
    except Exception as e:
        logger.error(f"Error registering enhanced solvers: {e}")