from models import TalkingAnime3
import torch
import socket
import pickle
from collections import OrderedDict

def server_program():
    host = '0.0.0.0'
    port = 11453
    model = TalkingAnime3().to(torch.device('cuda:0'))
    model = model.eval()
    server_socket = socket.socket()
    server_socket.bind((host, port))

    server_socket.listen(2)
    print("Server listening...")

    conn, address = server_socket.accept()
    print(f"Connection from: {address}")

    while True:
        data = conn.recv(4096)  # 接收数据
        if not data:
            break
        model.face_cache = OrderedDict()
        serialized_data = data
        received_data = pickle.loads(serialized_data)  # 解码数据
        output_image = model(received_data)
        serialized_result = pickle.dumps(output_image)  # 序列化结果
        conn.send(serialized_result)  # 发送结果
    conn.close()


if __name__ == '__main__':
    server_program()
