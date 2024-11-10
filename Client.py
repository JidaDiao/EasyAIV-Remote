import torch
import pyvirtualcam
import numpy as np
from multiprocessing import Value, Process, Queue
from args import args
import cv2
import socket
import warnings
import time

warnings.filterwarnings("ignore", category=UserWarning)


fps_delay = 0.01


class EasyAIV(Process):  #
    def __init__(self, ):
        super().__init__()
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    @torch.no_grad()
    def run(self):
        if args.output_webcam:
            cam_scale = 1
            cam_width_scale = 1
            if args.anime4k:
                cam_scale = 2
            if args.alpha_split:
                cam_width_scale = 2
            cam = pyvirtualcam.Camera(width=args.output_w * cam_scale * cam_width_scale,
                                      height=args.output_h * cam_scale,
                                      fps=30,
                                      backend=args.output_webcam,
                                      fmt=
                                      {'unitycapture': pyvirtualcam.PixelFormat.RGBA,
                                       'obs': pyvirtualcam.PixelFormat.RGB}[
                                          args.output_webcam])
            print(f'Using virtual camera: {cam.device}')
        while True:
            try:
                print(f"尝试连接 “192.168.50.13:11453”ing")
                self.client_socket.connect(("192.168.50.13", 11453))  # 替换为服务器地址
                print("连接上了！")
                try:
                    while True:
                        # 接收数据长度（前4个字节）
                        length_buf = self.client_socket.recv(4)
                        if not length_buf:
                            break
                        length = int.from_bytes(length_buf, 'big')

                        # 按长度接收数据
                        data = b''
                        while len(data) < length:
                            packet = self.client_socket.recv(length - len(data))
                            if not packet:
                                break
                            data += packet

                        if len(data) != length:
                            break

                        # 转换数据为NumPy数组
                        img_np = np.frombuffer(data, dtype=np.uint8)
                        result_image = cv2.imdecode(img_np, cv2.IMREAD_UNCHANGED)
                        # result_image = np.frombuffer(data, dtype=np.uint8).reshape((512, 512, 4))
                        cam.send(result_image)
                        cam.sleep_until_next_frame()
                except Exception as e:
                    print(f"Error during receiving data: {e}")
                finally:
                    self.client_socket.close()
            except (ConnectionRefusedError, socket.error) as e:
                print(f"连接失败: {e}. 5秒后尝试重新连接...")
                time.sleep(5)  # 等待5秒后重新尝试连接


if __name__ == '__main__':
    aiv = EasyAIV()
    aiv.start()
