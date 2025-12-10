import logging
import asyncio
from typing import Dict, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.strategies.runner import StrategyRunner

logger = logging.getLogger(__name__)

class StrategyScheduler:
    """
    Programador de tareas para ejecución de estrategias.
    
    Lee la configuración de 'schedule' de cada estrategia en strategies.yaml
    y programa su ejecución usando APScheduler.
    """
    
    def __init__(self, runner: StrategyRunner, config: Dict[str, Any]):
        """
        Inicializar scheduler.
        
        Args:
            runner: Instancia de StrategyRunner para ejecutar las estrategias
            config: Configuración completa (incluyendo sección 'strategies')
        """
        self.runner = runner
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self._jobs = {}
        
    def setup_jobs(self):
        """Configurar jobs basados en config."""
        strategies = self.config.get("strategies", {})
        
        for strategy_id, strat_conf in strategies.items():
            if not strat_conf.get("enabled", False):
                continue
                
            schedule = strat_conf.get("schedule")
            if not schedule:
                # Default fallback if no schedule provided: run every 1 hour? 
                # Or just skip if manual/event-based.
                # For MVP, let's assume manual/runner-loop if no schedule.
                continue
                
            trigger = None
            sched_type = schedule.get("type")
            
            if sched_type == "cron":
                # E.g. time: "09:30", days: "mon-fri"
                time_parts = schedule.get("time", "00:00").split(":")
                trigger = CronTrigger(
                    day_of_week=schedule.get("days", "*"),
                    hour=int(time_parts[0]),
                    minute=int(time_parts[1]),
                    timezone=schedule.get("timezone", "UTC")
                )
                
            elif sched_type == "interval":
                # E.g. minutes: 15 or hours: 1
                trigger = IntervalTrigger(
                    minutes=schedule.get("minutes", 0),
                    hours=schedule.get("hours", 0),
                    seconds=schedule.get("seconds", 0)
                )
                
            if trigger:
                job_id = f"job_{strategy_id}"
                self.scheduler.add_job(
                    self._run_job_wrapper,
                    trigger,
                    args=[strategy_id],
                    id=job_id,
                    replace_existing=True
                )
                self._jobs[strategy_id] = job_id
                logger.info(f"Programada estrategia '{strategy_id}': {sched_type} ({schedule})")

    async def _run_job_wrapper(self, strategy_id: str):
        """Wrapper para manejar ejecución de job."""
        logger.info(f"⏰ Scheduler activado para: {strategy_id}")
        await self.runner.run_single_strategy(strategy_id)
        
    def start(self):
        """Iniciar scheduler."""
        if not self.scheduler.running:
            self.setup_jobs()
            self.scheduler.start()
            logger.info("Strategy Scheduler iniciado.")
            
    def stop(self):
        """Detener scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Strategy Scheduler detenido.")
