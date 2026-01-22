from ultralytics import YOLO
model = YOLO('model/nepali_lp.pt')
print(model.names)