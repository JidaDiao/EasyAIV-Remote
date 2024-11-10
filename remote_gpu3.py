from models import TalkingAnime3
import torch

model = TalkingAnime3().to(torch.device('cuda:0'))
model = model.eval()
print("success")