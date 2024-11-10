import subprocess
import os


def execute_ssh_command():
    # 构建 SSH 命令
    ssh_command = (
        "ssh -t jxj@192.168.50.13 -p 11451 "
        "\"bash /home/jxj/start_server.sh\""
    )

    # 使用 subprocess 执行命令
    try:
        # Popen 允许你在后台运行
        process = subprocess.Popen(ssh_command, shell=True)
        print("Remote command executed, terminal will close.")
    except Exception as e:
        print("Error executing command:")
        print(e)


if __name__ == "__main__":
    execute_ssh_command()
    # 如果想要立即关闭本地终端，可以直接调用 os._exit()
    os._exit(0)