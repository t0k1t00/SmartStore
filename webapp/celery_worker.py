from celery import Celery
from celery.schedules import crontab
import logging

from .config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "smartstore",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,  # One task at a time (CPU-intensive)
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks (prevent memory leaks)
)

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'retrain-lstm-cache-hourly': {
        'task': 'webapp.celery_worker.train_lstm_cache',
        'schedule': crontab(minute=0),  # Every hour
        'args': ()
    },
    'retrain-isolation-forest-daily': {
        'task': 'webapp.celery_worker.train_isolation_forest',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        'args': ()
    },
    'run-prophet-forecast-daily': {
        'task': 'webapp.celery_worker.run_prophet_forecast',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
        'args': (30,)  # 30-day forecast
    },
    'run-dbscan-clustering-weekly': {
        'task': 'webapp.celery_worker.run_dbscan_clustering',
        'schedule': crontab(day_of_week=1, hour=4, minute=0),  # Monday 4 AM
        'args': ()
    },
}
@celery_app.task(bind=True, name='webapp.celery_worker.train_lstm_cache')
def train_lstm_cache(self):
    logger.info(" Starting LSTM cache model training...")
    
    try:
        from .ml.cache_lstm import LSTMCachePredictor
        
        # Update task state
        self.update_state(state='PROGRESS', meta={'status': 'Loading data...'})
        
        predictor = LSTMCachePredictor()
        
        self.update_state(state='PROGRESS', meta={'status': 'Training model...'})
        metrics = predictor.train()
        
        self.update_state(state='PROGRESS', meta={'status': 'Saving model...'})
        predictor.save_model()
        
        logger.info(f"✅ LSTM training complete. Metrics: {metrics}")
        
        return {
            'status': 'success',
            'metrics': metrics,
            'model_file': str(settings.CACHE_MODEL_FILE)
        }
    
    except Exception as e:
        logger.error(f" LSTM training failed: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }


@celery_app.task(bind=True, name='webapp.celery_worker.train_isolation_forest')
def train_isolation_forest(self):
    logger.info(" Starting Isolation Forest training...")
    
    try:
        from .ml.anomaly_iforest import IsolationForestDetector
        
        self.update_state(state='PROGRESS', meta={'status': 'Loading data...'})
        
        detector = IsolationForestDetector()
        
        self.update_state(state='PROGRESS', meta={'status': 'Training model...'})
        metrics = detector.train()
        
        self.update_state(state='PROGRESS', meta={'status': 'Saving model...'})
        detector.save_model()
        
        logger.info(f"✅ Isolation Forest training complete. Metrics: {metrics}")
        
        return {
            'status': 'success',
            'metrics': metrics,
            'model_file': str(settings.ANOMALY_MODEL_FILE)
        }
    
    except Exception as e:
        logger.error(f" Isolation Forest training failed: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }


@celery_app.task(bind=True, name='webapp.celery_worker.run_prophet_forecast')
def run_prophet_forecast(self, periods=30):
    logger.info(f" Starting Prophet forecast ({periods} days)...")
    
    try:
        from .ml.forecast_prophet import ProphetForecaster
        
        self.update_state(state='PROGRESS', meta={'status': 'Loading data...'})
        
        forecaster = ProphetForecaster()
        
        self.update_state(state='PROGRESS', meta={'status': 'Training model...'})
        forecaster.train()
        
        self.update_state(state='PROGRESS', meta={'status': 'Generating forecast...'})
        forecast = forecaster.predict(periods)
        
        self.update_state(state='PROGRESS', meta={'status': 'Saving model...'})
        forecaster.save_model()
        
        logger.info(f" Prophet forecast complete for {periods} days")
        
        return {
            'status': 'success',
            'forecast': forecast,
            'periods': periods,
            'model_file': str(settings.PROPHET_MODEL_FILE)
        }
    
    except Exception as e:
        logger.error(f" Prophet forecast failed: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }


@celery_app.task(bind=True, name='webapp.celery_worker.run_dbscan_clustering')
def run_dbscan_clustering(self):
    logger.info(" Starting DBSCAN clustering...")
    
    try:
        from .ml.cluster_dbscan import DBSCANClusterer
        
        self.update_state(state='PROGRESS', meta={'status': 'Loading data...'})
        
        clusterer = DBSCANClusterer()
        
        self.update_state(state='PROGRESS', meta={'status': 'Clustering...'})
        results = clusterer.fit()
        
        self.update_state(state='PROGRESS', meta={'status': 'Saving results...'})
        clusterer.save_model()
        
        logger.info(f" DBSCAN clustering complete. Clusters: {results['n_clusters']}")
        
        return {
            'status': 'success',
            'results': results,
            'model_file': str(settings.DBSCAN_MODEL_FILE)
        }
    
    except Exception as e:
        logger.error(f" DBSCAN clustering failed: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }


@celery_app.task(name='webapp.celery_worker.generate_synthetic_data')
def generate_synthetic_data(num_samples=1000):
    logger.info(f"🚀 Generating {num_samples} synthetic samples...")
    
    try:
        from .simulation.synthetic_generator import SyntheticDataGenerator
        
        generator = SyntheticDataGenerator()
        generator.fit()
        
        synthetic_data = generator.generate(num_samples)
        
        logger.info(f"✅ Generated {len(synthetic_data)} synthetic samples")
        
        return {
            'status': 'success',
            'num_samples': len(synthetic_data),
            'data': synthetic_data.to_dict('records')
        }
    
    except Exception as e:
        logger.error(f"❌ Synthetic data generation failed: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }
if __name__ == '__main__':
    celery_app.start()
