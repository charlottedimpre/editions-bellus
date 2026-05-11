import time
import docker
from ..models import ProcessStatus

def wait_for_celery(container):
    for i in range(20):
        try:
            result = container.exec_run("celery -A Stage inspect ping")
            output = result.output.decode()

            if "pong" in output:
                return True

        except Exception:
            pass

        time.sleep(1)

    return False