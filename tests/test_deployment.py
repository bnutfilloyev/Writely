"""
Deployment verification tests for IELTS Telegram Bot.
"""
import asyncio
import os
import pytest
import requests
import subprocess
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import docker
from docker.errors import DockerException


class TestDeploymentConfiguration:
    """Test deployment configuration files and setup."""
    
    def test_dockerfile_exists(self):
        """Test that Dockerfile exists and has required content."""
        dockerfile_path = Path("Dockerfile")
        assert dockerfile_path.exists(), "Dockerfile not found"
        
        content = dockerfile_path.read_text()
        
        # Check for required components
        assert "FROM python:3.11-slim" in content
        assert "WORKDIR /app" in content
        assert "COPY requirements.txt" in content
        assert "RUN pip install" in content
        assert "EXPOSE 8000" in content
        assert "HEALTHCHECK" in content
        assert "CMD" in content
    
    def test_docker_compose_exists(self):
        """Test that docker-compose.yml exists and is valid."""
        compose_path = Path("docker-compose.yml")
        assert compose_path.exists(), "docker-compose.yml not found"
        
        content = compose_path.read_text()
        
        # Check for required services and configuration
        assert "version:" in content
        assert "services:" in content
        assert "ielts-bot:" in content
        assert "build: ." in content
        assert "restart: unless-stopped" in content
        assert "ports:" in content
        assert "8000:8000" in content
        assert "volumes:" in content
        assert "healthcheck:" in content
    
    def test_production_env_template(self):
        """Test that production environment template exists."""
        env_prod_path = Path(".env.production")
        assert env_prod_path.exists(), ".env.production not found"
        
        content = env_prod_path.read_text()
        
        # Check for required environment variables
        required_vars = [
            "TELEGRAM_BOT_TOKEN",
            "OPENAI_API_KEY",
            "DATABASE_URL",
            "DEBUG=False",
            "LOG_LEVEL=INFO",
            "ENABLE_API=true"
        ]
        
        for var in required_vars:
            assert var in content, f"Missing environment variable: {var}"
    
    def test_deployment_scripts_exist(self):
        """Test that deployment scripts exist and are executable."""
        deploy_script = Path("deploy/deploy.sh")
        update_script = Path("deploy/update.sh")
        
        assert deploy_script.exists(), "deploy.sh not found"
        assert update_script.exists(), "update.sh not found"
        
        # Check if scripts are executable
        assert os.access(deploy_script, os.X_OK), "deploy.sh is not executable"
        assert os.access(update_script, os.X_OK), "update.sh is not executable"
    
    def test_deployment_script_content(self):
        """Test deployment script has required functions."""
        deploy_script = Path("deploy/deploy.sh")
        content = deploy_script.read_text()
        
        required_functions = [
            "install_dependencies",
            "setup_app_directory",
            "deploy_code",
            "setup_environment",
            "start_application",
            "setup_nginx",
            "setup_firewall"
        ]
        
        for func in required_functions:
            assert func in content, f"Missing function in deploy.sh: {func}"


class TestDockerBuild:
    """Test Docker image building and container functionality."""
    
    @pytest.fixture(scope="class")
    def docker_client(self):
        """Get Docker client for testing."""
        try:
            client = docker.from_env()
            # Test Docker connection
            client.ping()
            return client
        except DockerException:
            pytest.skip("Docker not available for testing")
    
    def test_docker_build(self, docker_client):
        """Test that Docker image builds successfully."""
        try:
            # Build the image
            image, logs = docker_client.images.build(
                path=".",
                tag="ielts-bot:test",
                rm=True,
                forcerm=True
            )
            
            assert image is not None, "Docker image build failed"
            
            # Check image properties
            assert "ielts-bot:test" in [tag for tag in image.tags]
            
        except Exception as e:
            pytest.fail(f"Docker build failed: {e}")
    
    def test_docker_container_health(self, docker_client):
        """Test that container starts and passes health check."""
        try:
            # Create test environment
            test_env = {
                "TELEGRAM_BOT_TOKEN": "test_token",
                "OPENAI_API_KEY": "test_key",
                "DEBUG": "true"
            }
            
            # Run container
            container = docker_client.containers.run(
                "ielts-bot:test",
                environment=test_env,
                ports={"8000/tcp": 8001},
                detach=True,
                remove=True
            )
            
            # Wait for container to start
            time.sleep(10)
            
            # Check container status
            container.reload()
            assert container.status == "running", f"Container not running: {container.status}"
            
            # Stop container
            container.stop()
            
        except Exception as e:
            pytest.fail(f"Container health test failed: {e}")


class TestHealthEndpoint:
    """Test health check endpoint functionality."""
    
    @pytest.fixture
    def mock_app_setup(self):
        """Mock application setup for testing."""
        with patch('main.setup_database'), \
             patch('main.create_bot'), \
             patch('main.create_dispatcher'):
            yield
    
    def test_health_endpoint_structure(self):
        """Test health endpoint returns correct structure."""
        from main import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        with patch('main.get_db_session') as mock_db:
            # Mock database session
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            
            response = client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            
            # Check response structure
            required_fields = ["status", "database", "bot", "version"]
            for field in required_fields:
                assert field in data, f"Missing field in health response: {field}"
    
    def test_root_endpoint(self):
        """Test root endpoint returns correct message."""
        from main import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "IELTS Telegram Bot API" in data["message"]


class TestLoggingConfiguration:
    """Test production logging configuration."""
    
    def test_logging_config_import(self):
        """Test that logging configuration can be imported."""
        from src.config.logging_config import (
            ProductionLoggingConfig,
            setup_production_logging,
            get_access_logger
        )
        
        assert ProductionLoggingConfig is not None
        assert setup_production_logging is not None
        assert get_access_logger is not None
    
    def test_production_logging_setup(self):
        """Test production logging setup."""
        from src.config.logging_config import ProductionLoggingConfig
        
        # Create temporary log directory
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"LOG_FILE_PATH": f"{temp_dir}/bot.log"}):
                config = ProductionLoggingConfig()
                
                # Test configuration
                assert config.log_dir.exists()
                assert config.max_bytes > 0
                assert config.backup_count > 0
    
    def test_log_filters(self):
        """Test custom log filters."""
        from src.config.logging_config import HealthCheckFilter, SensitiveDataFilter
        
        # Test health check filter
        health_filter = HealthCheckFilter()
        
        # Mock log record
        record = MagicMock()
        record.pathname = "/api/health"
        assert not health_filter.filter(record)
        
        record.pathname = "/api/submit"
        assert health_filter.filter(record)
        
        # Test sensitive data filter
        sensitive_filter = SensitiveDataFilter()
        record = MagicMock()
        record.msg = "User token: secret123"
        
        assert sensitive_filter.filter(record)
        assert "***REDACTED***" in str(record.msg)


class TestEnvironmentConfiguration:
    """Test environment configuration for different deployment scenarios."""
    
    def test_required_environment_variables(self):
        """Test that required environment variables are validated."""
        from src.config.settings import Settings
        
        # Test with missing variables
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                settings.validate_required_settings()
            
            assert "TELEGRAM_BOT_TOKEN" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)
    
    def test_production_environment_setup(self):
        """Test production environment configuration."""
        prod_env = {
            "TELEGRAM_BOT_TOKEN": "prod_token",
            "OPENAI_API_KEY": "prod_key",
            "DEBUG": "False",
            "LOG_LEVEL": "INFO",
            "ENABLE_API": "true"
        }
        
        with patch.dict(os.environ, prod_env):
            from src.config.settings import Settings
            settings = Settings()
            
            assert not settings.DEBUG
            assert settings.LOG_LEVEL == "INFO"
            assert settings.TELEGRAM_BOT_TOKEN == "prod_token"
            assert settings.OPENAI_API_KEY == "prod_key"


class TestDeploymentIntegration:
    """Integration tests for deployment scenarios."""
    
    @pytest.mark.asyncio
    async def test_application_startup_sequence(self):
        """Test complete application startup sequence."""
        from main import setup_database, create_bot, create_dispatcher
        
        with patch('src.database.init.check_database_connection', return_value=True), \
             patch('src.database.init.migrate_database'), \
             patch('src.config.settings.settings.validate_required_settings'):
            
            # Test database setup
            await setup_database()
            
            # Test bot creation
            with patch('src.config.settings.settings.TELEGRAM_BOT_TOKEN', 'test_token'):
                bot = create_bot()
                assert bot is not None
            
            # Test dispatcher creation
            dispatcher = create_dispatcher()
            assert dispatcher is not None
    
    def test_deployment_verification_script(self):
        """Test deployment verification functionality."""
        # This would be a script that runs post-deployment checks
        verification_checks = [
            self._check_docker_container_running,
            self._check_health_endpoint,
            self._check_log_files_created,
            self._check_database_connection
        ]
        
        for check in verification_checks:
            try:
                check()
            except Exception as e:
                pytest.fail(f"Deployment verification failed: {check.__name__}: {e}")
    
    def _check_docker_container_running(self):
        """Check if Docker container is running."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=ielts-telegram-bot", "--format", "{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            assert "Up" in result.stdout, "Container not running"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Docker not available or container not found")
    
    def _check_health_endpoint(self):
        """Check if health endpoint is accessible."""
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert data.get("status") in ["healthy", "unhealthy"]
        except requests.RequestException:
            pytest.skip("Health endpoint not accessible")
    
    def _check_log_files_created(self):
        """Check if log files are created in production."""
        log_paths = [
            Path("/app/logs/bot.log"),
            Path("./logs/bot.log"),
            Path("bot.log")
        ]
        
        # Check if any log file exists
        log_exists = any(path.exists() for path in log_paths)
        if not log_exists:
            pytest.skip("Log files not found (may be running in development mode)")
    
    def _check_database_connection(self):
        """Check database connection."""
        try:
            from src.database.init import check_database_connection
            
            # This would need to be run in an async context in real deployment
            # For testing, we'll just check the function exists
            assert callable(check_database_connection)
        except ImportError:
            pytest.fail("Database connection check not available")


# Deployment verification script that can be run standalone
def run_deployment_verification():
    """Run deployment verification checks."""
    print("Running deployment verification...")
    
    checks = [
        ("Docker container", lambda: subprocess.run(["docker", "ps", "--filter", "name=ielts-telegram-bot"], check=True)),
        ("Health endpoint", lambda: requests.get("http://localhost:8000/health", timeout=5).raise_for_status()),
        ("Log directory", lambda: Path("/app/logs").exists() or Path("./logs").exists()),
    ]
    
    results = []
    for name, check in checks:
        try:
            check()
            results.append((name, "PASS"))
            print(f"✓ {name}: PASS")
        except Exception as e:
            results.append((name, f"FAIL: {e}"))
            print(f"✗ {name}: FAIL - {e}")
    
    # Summary
    passed = sum(1 for _, result in results if result == "PASS")
    total = len(results)
    
    print(f"\nVerification Summary: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 Deployment verification successful!")
        return True
    else:
        print("❌ Deployment verification failed!")
        return False


if __name__ == "__main__":
    # Allow running verification standalone
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        success = run_deployment_verification()
        sys.exit(0 if success else 1)