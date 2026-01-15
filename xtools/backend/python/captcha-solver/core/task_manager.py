import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from models.base import TaskStatus, TaskMetadata
from models.responses import TaskResultResponse
from utils.logger import get_logger
from utils.cache_utils import cache_manager
from config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class TaskManager:
    """Manages CAPTCHA solving tasks with async processing and caching."""
    
    def __init__(self):
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.completed_tasks: Dict[str, Dict[str, Any]] = {}
        self.task_queue = asyncio.Queue()
        self.worker_tasks: List[asyncio.Task] = []
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'processing_tasks': 0
        }
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._workers_started = False
    
    async def start_workers(self, num_workers: int = None) -> None:
        """Start background worker tasks."""
        if self._workers_started:
            return
        
        num_workers = num_workers or settings.max_concurrent_tasks
        
        logger.info(f"Starting {num_workers} task workers")
        
        for i in range(num_workers):
            worker_task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_tasks.append(worker_task)
        
        self._cleanup_task = asyncio.create_task(self._cleanup_completed_tasks())
        
        self._workers_started = True
        logger.info(f"Task manager started with {num_workers} workers")
    
    async def stop_workers(self) -> None:
        """Stop all worker tasks."""
        if not self._workers_started:
            return
        
        logger.info("Stopping task workers")
        
        for task in self.worker_tasks:
            task.cancel()
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        await asyncio.gather(*self.worker_tasks, self._cleanup_task, return_exceptions=True)
        
        self.worker_tasks.clear()
        self._cleanup_task = None
        self._workers_started = False
        
        logger.info("Task workers stopped")
    
    async def create_task(
        self,
        captcha_type: str,
        task_data: Dict[str, Any],
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Create a new CAPTCHA solving task."""
        task_id = str(uuid.uuid4())
        
        metadata = TaskMetadata(
            task_id=task_id,
            client_ip=client_ip,
            user_agent=user_agent,
            timeout_seconds=task_data.get('timeout', settings.task_timeout)
        )
        
        task_record = {
            'task_id': task_id,
            'captcha_type': captcha_type,
            'status': TaskStatus.PENDING,
            'data': task_data,
            'metadata': metadata,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'result': None,
            'error': None,
            'attempts': 0
        }
        
        async with self._lock:
            self.active_tasks[task_id] = task_record
            self.stats['total_tasks'] += 1
        
        await self.task_queue.put(task_id)
        
        logger.info(f"Created task {task_id} for {captcha_type}")
        return task_id
    
    async def get_task_result(self, task_id: str) -> Optional[TaskResultResponse]:
        """Get the result of a task."""
        async with self._lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                return self._create_task_response(task)
            
            if task_id in self.completed_tasks:
                task = self.completed_tasks[task_id]
                return self._create_task_response(task)
        
        cached_result = await cache_manager.get_cached_task_result(task_id)
        if cached_result:
            return TaskResultResponse(**cached_result)
        
        return None
    
    def _create_task_response(self, task: Dict[str, Any]) -> TaskResultResponse:
        """Create a TaskResultResponse from task data."""
        processing_time = None
        if task.get('completed_at') and task.get('created_at'):
            processing_time = (task['completed_at'] - task['created_at']).total_seconds()
        
        result = task.get('result')
        
        solution = result
        if isinstance(result, dict) and 'solution_type' in result:
            from models.responses import TokenSolution, TextSolution, ImageGridSolution, AudioSolution, RotationSolution, DiceSolution
            
            solution_type = result.get('solution_type')
            if solution_type == 'token':
                solution = TokenSolution(**result)
            elif solution_type == 'text':
                solution = TextSolution(**result)
            elif solution_type == 'image_grid':
                solution = ImageGridSolution(**result)
            elif solution_type == 'audio':
                solution = AudioSolution(**result)
            elif solution_type == 'rotation':
                solution = RotationSolution(**result)
            elif solution_type == 'dice':
                solution = DiceSolution(**result)
        
        response = TaskResultResponse(
            task_id=task['task_id'],
            status=task['status'],
            captcha_type=task.get('captcha_type'),
            solution=solution,
            error_message=task.get('error'),
            created_at=task['created_at'],
            completed_at=task.get('completed_at'),
            processing_time=processing_time,
            attempts=task.get('attempts', 0)
        )
        
        return response
    
    async def _worker(self, worker_name: str) -> None:
        """Background worker to process tasks."""
        logger.debug(f"Worker {worker_name} started")
        
        while True:
            try:
                task_id = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                
                async with self._lock:
                    if task_id not in self.active_tasks:
                        continue
                    
                    task = self.active_tasks[task_id]
                    task['status'] = TaskStatus.PROCESSING
                    task['updated_at'] = datetime.utcnow()
                    self.stats['processing_tasks'] += 1
                
                logger.debug(f"Worker {worker_name} processing task {task_id}")
                
                await self._process_task(task_id, worker_name)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.debug(f"Worker {worker_name} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                continue
    
    async def _process_task(self, task_id: str, worker_name: str) -> None:
        """Process a single task."""
        try:
            async with self._lock:
                if task_id not in self.active_tasks:
                    return
                
                task = self.active_tasks[task_id]
                task['attempts'] += 1
            
            from .solver_factory import solver_factory
            
            solver = solver_factory.get_solver(task['captcha_type'])
            if not solver:
                await self._mark_task_failed(task_id, f"No solver available for {task['captcha_type']}")
                return
            
            cached_solution = await cache_manager.get_cached_solution(task['data'])
            if cached_solution:
                logger.info(f"Using cached solution for task {task_id}")
                await self._mark_task_completed(task_id, cached_solution)
                return
            
            timeout = task['metadata'].timeout_seconds
            
            try:
                result = await asyncio.wait_for(
                    solver.solve(task['data']),
                    timeout=timeout
                )
                
                if result:
                    await cache_manager.cache_captcha_solution(task['data'], result)
                    await self._mark_task_completed(task_id, result)
                else:
                    await self._handle_task_retry(task_id, "Solver returned no result")
                
            except asyncio.TimeoutError:
                await self._handle_task_retry(task_id, f"Task timeout after {timeout} seconds")
            except Exception as e:
                await self._handle_task_retry(task_id, f"Solver error: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
            await self._mark_task_failed(task_id, f"Processing error: {str(e)}")
    
    async def _handle_task_retry(self, task_id: str, error_message: str) -> None:
        """Handle task retry logic."""
        async with self._lock:
            if task_id not in self.active_tasks:
                return
            
            task = self.active_tasks[task_id]
            max_attempts = task['metadata'].max_attempts
            
            if task['attempts'] < max_attempts:
                task['status'] = TaskStatus.PENDING
                task['updated_at'] = datetime.utcnow()
                task['error'] = f"Attempt {task['attempts']}: {error_message}"
                
                await self.task_queue.put(task_id)
                logger.info(f"Retrying task {task_id} (attempt {task['attempts']}/{max_attempts})")
            else:
                await self._mark_task_failed(task_id, f"Max attempts reached. Last error: {error_message}")
    
    async def _mark_task_completed(self, task_id: str, result: Any) -> None:
        """Mark a task as completed."""
        
        async with self._lock:
            if task_id not in self.active_tasks:
                return
            
            task = self.active_tasks[task_id]
            task['status'] = TaskStatus.COMPLETED
            task['result'] = result
            task['completed_at'] = datetime.utcnow()
            task['updated_at'] = datetime.utcnow()
            
            self.completed_tasks[task_id] = task
            del self.active_tasks[task_id]
            
            self.stats['completed_tasks'] += 1
            self.stats['processing_tasks'] -= 1
        
        await cache_manager.cache_task_result(task_id, self._create_task_response(task).model_dump())
        
        logger.info(f"Task {task_id} completed successfully")
    
    async def _mark_task_failed(self, task_id: str, error_message: str) -> None:
        """Mark a task as failed."""
        async with self._lock:
            if task_id not in self.active_tasks:
                return
            
            task = self.active_tasks[task_id]
            task['status'] = TaskStatus.FAILED
            task['error'] = error_message
            task['completed_at'] = datetime.utcnow()
            task['updated_at'] = datetime.utcnow()
            
            self.completed_tasks[task_id] = task
            del self.active_tasks[task_id]
            
            self.stats['failed_tasks'] += 1
            self.stats['processing_tasks'] -= 1
        
        await cache_manager.cache_task_result(task_id, self._create_task_response(task).model_dump())
        
        logger.warning(f"Task {task_id} failed: {error_message}")
    
    async def _cleanup_completed_tasks(self) -> None:
        """Periodically clean up old completed tasks."""
        while True:
            try:
                await asyncio.sleep(settings.task_cleanup_interval)
                
                cutoff_time = datetime.utcnow() - timedelta(hours=1)
                
                async with self._lock:
                    tasks_to_remove = []
                    for task_id, task in self.completed_tasks.items():
                        if task.get('completed_at', datetime.utcnow()) < cutoff_time:
                            tasks_to_remove.append(task_id)
                    
                    for task_id in tasks_to_remove:
                        del self.completed_tasks[task_id]
                
                if tasks_to_remove:
                    logger.debug(f"Cleaned up {len(tasks_to_remove)} old completed tasks")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    async def get_task_stats(self) -> Dict[str, Any]:
        """Get task processing statistics."""
        async with self._lock:
            active_count = len(self.active_tasks)
            completed_count = len(self.completed_tasks)
            
            total_finished = self.stats['completed_tasks'] + self.stats['failed_tasks']
            success_rate = (self.stats['completed_tasks'] / total_finished * 100) if total_finished > 0 else 0
            
            return {
                'total_tasks': self.stats['total_tasks'],
                'active_tasks': active_count,
                'completed_tasks': completed_count,
                'processing_tasks': self.stats['processing_tasks'],
                'success_rate': round(success_rate, 2),
                'queue_size': self.task_queue.qsize(),
                'workers_active': len(self.worker_tasks),
                'cache_stats': await cache_manager.get_cache_stats()
            }
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or processing task."""
        async with self._lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task['status'] in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
                    task['status'] = TaskStatus.FAILED
                    task['error'] = "Task cancelled by user"
                    task['completed_at'] = datetime.utcnow()
                    task['updated_at'] = datetime.utcnow()
                    
                    self.completed_tasks[task_id] = task
                    del self.active_tasks[task_id]
                    
                    self.stats['failed_tasks'] += 1
                    if task['status'] == TaskStatus.PROCESSING:
                        self.stats['processing_tasks'] -= 1
                    
                    logger.info(f"Task {task_id} cancelled")
                    return True
        
        return False
    
    async def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get list of active tasks."""
        async with self._lock:
            return [
                {
                    'task_id': task['task_id'],
                    'captcha_type': task['captcha_type'],
                    'status': task['status'],
                    'created_at': task['created_at'].isoformat(),
                    'attempts': task['attempts']
                }
                for task in self.active_tasks.values()
            ]


task_manager = TaskManager()