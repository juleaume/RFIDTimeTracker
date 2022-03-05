from paramiko.client import SSHClient, AutoAddPolicy
from logger import logger

RobotIP = '192.168.1.5'
RobotPort = 22
RobotID = 'pi'
RobotPW = 'raspberry'


class BoardConnection(SSHClient):
    def __init__(self):
        super(BoardConnection, self).__init__()
        self.set_missing_host_key_policy(AutoAddPolicy)
        self.connect(RobotIP, RobotPort, RobotID, RobotPW)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return True


def upload_code():
    # Copy Python files to the Raspberry
    logger.info('Upload code...')
    file_list = [
        "client.py", "logger.py", "bluetooth_manager.py", "communication.py"
    ]
    with BoardConnection() as client:
        with client.open_sftp() as scp:
            for file in file_list:
                scp.put(file, f"/home/{RobotID}/{file}")
    logger.info('Board code successfully uploaded !')


if __name__ == '__main__':
    upload_code()
