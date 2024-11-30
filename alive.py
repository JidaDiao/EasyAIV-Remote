import socket

import numpy as np
from multiprocessing import Value, Process, Queue
import librosa
import time
import pygame
import pickle


def error_speech():
    pygame.mixer.init()
    pygame.mixer.music.load('data/speech/error-svc.wav')
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():  # 在音频播放为完成之前不退出程序
        time.sleep(0.1)  # 减轻循环负担
    pygame.quit()


def generate_voice_data(speech_path, mouth_offset=0.0):
    # 提取节奏强度
    time_ratio = 0.06
    y, sr = librosa.load(speech_path)
    frame_intervals = int(sr * time_ratio)
    voice_strengths = np.array([np.max(y[i:i + frame_intervals]) for i in range(0, len(y), frame_intervals)])
    voice_strengths[voice_strengths >= 0.1] += mouth_offset
    voice_strengths = np.clip(voice_strengths, 0., 1.).tolist()
    voice_strengths = [round(vst, 2) for i, vst in enumerate(voice_strengths)]
    voice_times = [0]
    last = time_ratio
    for i in range(len(voice_strengths)):
        voice_times.append(round(last, 1))
        last += time_ratio
    return voice_times, voice_strengths


def generate_beat_data(music_path, beat=2):
    # 提取音频节奏
    # beat取值1，2，4，控制点头节奏速度
    if beat not in [1, 2, 4]:
        beat = 2
    y, sr = librosa.load(music_path)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    beat_times = np.concatenate([[0], beat_times]).tolist()
    beat_times = [round(bt, 2) for bt in beat_times[::beat]]
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    frame_intervals = int(len(y) / len(onset_env))
    beat_strengths = np.array([np.max(y[i:i + frame_intervals]) for i in range(0, len(y), frame_intervals)])
    beat_strengths = np.clip(beat_strengths[beat_frames[::beat]], 0., 1.).tolist()
    return beat_times, beat_strengths


class AliveS(Process):
    def __init__(self, alive_args):  #
        super().__init__()
        self.is_speech = alive_args['is_speech']
        self.speech_q = alive_args['speech_q']

        self.is_singing = alive_args['is_singing']
        self.is_music_play = alive_args['is_music_play']
        self.beat_q = alive_args['beat_q']
        self.mouth_q = alive_args['mouth_q']
        #################
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("0.0.0.0", 11455))
        self.server_socket.listen(1)
        #################
        self.connection = None
        self.address = None

    def run(self):
        print("服务器正在运行，等待连接...")

        while True:
            try:
                # 接受一个客户端连接，并保持连接
                if self.connection is None:
                    self.connection, self.address = self.server_socket.accept()
                    print(f"AliveS接受到来自 {self.address} 的连接")
                else:
                    time.sleep(0.1)  # 保持连接，无需额外处理
            except Exception as ex:
                print(f"发生错误: {ex}")
                self.connection = None  # 出现异常时清除当前连接

    def speak(self, speech_path):
        try:
            while True:
                if self.connection is not None:
                    print(f"发送语音路径: {speech_path}")
                    self.connection.sendall(speech_path.encode('utf-8'))
                    response = self.connection.recv(1024)
                    received_data = pickle.loads(response)
                    voice_times, voice_strengths = received_data  # 解包成两个列表
                    self.speech_q.put_nowait({'voice_strengths': voice_strengths,
                                              'voice_times': voice_times})
                    self.is_speech.value = True

                    # 等待客户端响应 (例如 "播放结束")
                    response = self.connection.recv(1024).decode('utf-8')
                    print(f"收到客户端响应: {response}")

                    if response == "播放结束":
                        self.is_speech.value = False
                        print("语音播放已结束。")
                else:
                    print("??????")

        except Exception as ex:
            print(f"发送语音路径时发生错误: {ex}")
            self.connection = None  # 关闭并清理连接

    def sing(self, music_path, voice_path, mouth_offset, beat):
        try:
            beat_times, beat_strengths = generate_beat_data(music_path, beat)
            voice_times, voice_strengths = generate_voice_data(voice_path, mouth_offset)

            self.beat_q.put_nowait({'beat_times': np.array(beat_times) + time.perf_counter() - 0.15,
                                    'beat_strengths': beat_strengths})
            self.mouth_q.put_nowait({'voice_times': np.array(voice_times) + time.perf_counter() - 0.15,
                                     'voice_strengths': voice_strengths})
            self.is_singing.value = True

            # 播放
            pygame.mixer.init()
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and self.is_singing.value:  # 在音频播放为完成之前不退出程序
                time.sleep(0.1)  # 减轻循环负担
            pygame.quit()
            self.is_singing.value = False
        except Exception as ex:
            print(ex)
            error_speech()

    def rhythm(self, music_path, beat):
        try:
            # # 淡入淡出
            # sr, music_data = wavfile.read(music_path)
            # factors = np.arange(sr) / sr
            # factors = np.concatenate([factors, np.ones(len(music_data) - 2 * sr), factors[::-1]])
            # music_data = music_data * factors
            # music_data = np.clip(music_data, -32767, 32767)
            # wavfile.write(music_path, sr, music_data.astype(np.int16))

            # 提取节奏点，节奏强度
            beat_times, beat_strengths = generate_beat_data(music_path, beat)

            self.beat_q.put_nowait({'beat_times': np.array(beat_times) + time.perf_counter() - 0.15,
                                    'beat_strengths': beat_strengths})
            self.is_music_play.value = True
            # 播放
            pygame.mixer.init()
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and self.is_music_play.value:  # 在音频播放为完成之前不退出程序
                time.sleep(0.1)  # 减轻循环负担
            pygame.quit()
            self.is_music_play.value = False
        except Exception as ex:
            print(ex)
            error_speech()


class Alive(Process):
    def __init__(self, alive_args):  #
        super().__init__()
        self.is_speech = alive_args['is_speech']
        self.speech_q = alive_args['speech_q']

        self.is_singing = alive_args['is_singing']
        self.is_music_play = alive_args['is_music_play']
        self.beat_q = alive_args['beat_q']
        self.mouth_q = alive_args['mouth_q']

    def speak(self, speech_path):
        try:
            voice_times, voice_strengths = generate_voice_data(speech_path)

            self.speech_q.put_nowait({'voice_strengths': voice_strengths,
                                      'voice_times': np.array(voice_times) + time.perf_counter() - 0.15})
            self.is_speech.value = True

            # 播放
            pygame.mixer.init()
            pygame.mixer.music.load(speech_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and self.is_speech.value:  # 在音频播放为完成之前不退出程序
                time.sleep(0.1)  # 减轻循环负担
            pygame.quit()
            self.is_speech.value = False
        except Exception as ex:
            print(ex)
            error_speech()

    def sing(self, music_path, voice_path, mouth_offset, beat):
        try:
            beat_times, beat_strengths = generate_beat_data(music_path, beat)
            voice_times, voice_strengths = generate_voice_data(voice_path, mouth_offset)

            self.beat_q.put_nowait({'beat_times': np.array(beat_times) + time.perf_counter() - 0.15,
                                    'beat_strengths': beat_strengths})
            self.mouth_q.put_nowait({'voice_times': np.array(voice_times) + time.perf_counter() - 0.15,
                                     'voice_strengths': voice_strengths})
            self.is_singing.value = True

            # 播放
            pygame.mixer.init()
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and self.is_singing.value:  # 在音频播放为完成之前不退出程序
                time.sleep(0.1)  # 减轻循环负担
            pygame.quit()
            self.is_singing.value = False
        except Exception as ex:
            print(ex)
            error_speech()

    def rhythm(self, music_path, beat):
        try:
            # # 淡入淡出
            # sr, music_data = wavfile.read(music_path)
            # factors = np.arange(sr) / sr
            # factors = np.concatenate([factors, np.ones(len(music_data) - 2 * sr), factors[::-1]])
            # music_data = music_data * factors
            # music_data = np.clip(music_data, -32767, 32767)
            # wavfile.write(music_path, sr, music_data.astype(np.int16))

            # 提取节奏点，节奏强度
            beat_times, beat_strengths = generate_beat_data(music_path, beat)

            self.beat_q.put_nowait({'beat_times': np.array(beat_times) + time.perf_counter() - 0.15,
                                    'beat_strengths': beat_strengths})
            self.is_music_play.value = True
            # 播放
            pygame.mixer.init()
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and self.is_music_play.value:  # 在音频播放为完成之前不退出程序
                time.sleep(0.1)  # 减轻循环负担
            pygame.quit()
            self.is_music_play.value = False
        except Exception as ex:
            print(ex)
            error_speech()


class Voice(Process):
    def __init__(self):  #
        super().__init__()

    def run(self):
        while True:
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # 创建新的socket
                self.client_socket.connect(("192.168.50.13", 11455))
                while True:
                    speech_path = self.client_socket.recv(1024).decode('utf-8')
                    self.speak(speech_path)


            except (ConnectionResetError, BrokenPipeError, socket.error, pygame.error) as e:
                print(f"错误：{e}")
                print("服务器连接中断了，等待重新连接...")
                time.sleep(2)  # 等待 2 秒再重新连接

    def speak(self, speech_path):
        try:
            voice_times, voice_strengths = generate_voice_data(speech_path)
            data_to_send = (np.array(voice_times) + time.perf_counter() - 0.15, voice_strengths)
            serialized_data = pickle.dumps(data_to_send)
            self.client_socket.send(serialized_data)

            # 播放
            pygame.mixer.init()
            pygame.mixer.music.load(speech_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():  # 在音频播放为完成之前不退出程序
                time.sleep(0.1)  # 减轻循环负担
            pygame.quit()
            self.client_socket.sendall("播放结束".encode('utf-8'))
        except Exception as ex:
            print(ex)
            error_speech()

    # def sing(self, music_path, voice_path, mouth_offset, beat):
    #     try:
    #         beat_times, beat_strengths = generate_beat_data(music_path, beat)
    #         voice_times, voice_strengths = generate_voice_data(voice_path, mouth_offset)
    #
    #         self.beat_q.put_nowait({'beat_times': np.array(beat_times) + time.perf_counter() - 0.15,
    #                                 'beat_strengths': beat_strengths})
    #         self.mouth_q.put_nowait({'voice_times': np.array(voice_times) + time.perf_counter() - 0.15,
    #                                  'voice_strengths': voice_strengths})
    #         self.is_singing.value = True
    #
    #         # 播放
    #         pygame.mixer.init()
    #         pygame.mixer.music.load(music_path)
    #         pygame.mixer.music.play()
    #         while pygame.mixer.music.get_busy() and self.is_singing.value:  # 在音频播放为完成之前不退出程序
    #             time.sleep(0.1)  # 减轻循环负担
    #         pygame.quit()
    #         self.is_singing.value = False
    #     except Exception as ex:
    #         print(ex)
    #         error_speech()
    #
    # def rhythm(self, music_path, beat):
    #     try:
    #         # # 淡入淡出
    #         # sr, music_data = wavfile.read(music_path)
    #         # factors = np.arange(sr) / sr
    #         # factors = np.concatenate([factors, np.ones(len(music_data) - 2 * sr), factors[::-1]])
    #         # music_data = music_data * factors
    #         # music_data = np.clip(music_data, -32767, 32767)
    #         # wavfile.write(music_path, sr, music_data.astype(np.int16))
    #
    #         # 提取节奏点，节奏强度
    #         beat_times, beat_strengths = generate_beat_data(music_path, beat)
    #
    #         self.beat_q.put_nowait({'beat_times': np.array(beat_times) + time.perf_counter() - 0.15,
    #                                 'beat_strengths': beat_strengths})
    #         self.is_music_play.value = True
    #         # 播放
    #         pygame.mixer.init()
    #         pygame.mixer.music.load(music_path)
    #         pygame.mixer.music.play()
    #         while pygame.mixer.music.get_busy() and self.is_music_play.value:  # 在音频播放为完成之前不退出程序
    #             time.sleep(0.1)  # 减轻循环负担
    #         pygame.quit()
    #         self.is_music_play.value = False
    #     except Exception as ex:
    #         print(ex)
    #         error_speech()

# if __name__ == "__main__":
#     error_speech()
