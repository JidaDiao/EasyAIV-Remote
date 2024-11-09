import socket
import torch
import pickle
from collections import OrderedDict
from models import TalkingAnime3
# 服务器配置
HOST = '0.0.0.0'  # 监听所有可用接口
PORT = 11453  # 服务器监听端口




# 服务器端代码
def server():
    model = TalkingAnime3().to(torch.device('cuda:0'))
    model = model.eval()
    # 创建 socket 对象
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        # 绑定服务器地址和端口
        server_socket.bind((HOST, PORT))
        server_socket.listen()

        print(f"服务器正在监听 {HOST}:{PORT}...")

        # 等待客户端连接
        conn, addr = server_socket.accept()
        with conn:
            print(f"已连接到客户端：{addr}")

            while True:
                # 接收客户端数据（数据长度是已知的）
                data_len = conn.recv(4)
                if not data_len:
                    break

                data_len = int.from_bytes(data_len, 'big')
                data = conn.recv(data_len)

                # 反序列化数据
                params = pickle.loads(data)
                if params[-1]:
                    model.face_cache = OrderedDict()
                # 运行模型
                output = model(params[:-1])

                # 将模型的输出返回给客户端
                response = pickle.dumps(output)
                response_len = len(response).to_bytes(4, 'big')
                conn.sendall(response_len + response)


# 启动服务器
if __name__ == "__main__":
    server()