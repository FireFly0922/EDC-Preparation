# 数据集准备
[打标签](https://www.makesense.ai/)
# 训练
服务器训练，先把数据集 scp 传上去
```
scp -r "D:\大写数字数据集\dataset" mdz@remote3.ginpie.com:~/yolo11n_test/
```
创建 .yaml 文件
```
mkdir -p ~/yolo11n_test/configs
nano ~/yolo11n_test/configs/dataset.yaml
```
在 nano 编辑器中写 yaml 文件
```
path: /home/你的用户名/yolo_workspace/datasets/my_dataset

train: train/images
val: valid/images
test: test/images

names:
  0: A
  1: B
  2: C
  3: D
```
保存：Ctrl + o → Enter → Ctrl + x
```
yolo detect train \
model=yolo11n.pt \
data=~/yolo11n_test/configs/dataset.yaml \
epochs=5 \
imgsz=640 \
batch=8 \
workers=4 \
device=0 \
project=~/yolo11n_test/runs \
name=yolo11n_test
```
导出时候在 runs 里找 weights ，需要 best.pt 文件传回本地
```
scp mdz@remote3.ginpie.com:~/yolo11n_test/runs/detect/train-2/weights/best.pt "D:\yolo11n_test\"
```

# 部署
## 图形化界面
docker name:
sophgo/tpuc_dev:v3.4                d46a29a349f1       9.87GB         2.16GB
实际使用：
先开 docker (name:tpu-env)
```
cd D:\
cd maix_converter_platform
conda activate maix-converter
uvicorn web.app:app --host 0.0.0.0 --port 8000
```
[浏览器访问](http://127.0.0.1:8000)：图形化界面==难用的相思==
这里使用的数据集不是之前训练时的数据集，是其中一部分且没有标签（仅图片）
但是这个方法由于写死算子，成功率极低
## 手搓
1. 从 .pt → .onnx 开始
```py
from ultralytics import YOLO

model = YOLO("best.pt")

head = model.model.model[-1]
if hasattr(head, "end2end"):
    head.end2end = False

model.export(
    format="onnx",
    imgsz=[224, 320],
    dynamic=False,
    simplify=True,
    opset=17,
    nms=False
)
```
2. 通过 inspect_onnx.py 检查 onnx
   确认模型真实 onnx 节点名，决定从模型图的哪个位置“截断”给 NPU 编译
3. 将 Docker 挂在到 best.onnx 所在文件夹，启动容器
```
cd D:\yolo11n_test
docker run -it --rm --mount "type=bind,source=D:\yolo11n_test,target=/workspace" -w /workspace maixcam-tpumlir:v3.4 bash
```
4. .onnx → .mlir
```
model_transform.py \
  --model_name best \
  --model_def best.onnx \
  --input_shapes "[[1,3,224,320]]" \
  --mean "0,0,0" \
  --scale "0.00392156862745098,0.00392156862745098,0.00392156862745098" \
  --keep_aspect_ratio \
  --pixel_format rgb \
  --channel_format nchw \
  --output_names "/model.23/Concat_output_0,/model.23/Concat_1_output_0,/model.23/Concat_2_output_0" \
  --mlir best.mlir
```
5. INT8 校准：best.mlir → best_cali_table
   此处 image 不是数据集，而是没有标签的真实场景
```
run_calibration.py best.mlir \
  --dataset ./images \
  --input_num 104 \
  -o best_cali_table
```
6. 编译部署：best.mlir + best_cali_table → best.cvimodel
```
mkdir -p out

model_deploy.py \
  --mlir best.mlir \
  --quantize INT8 \
  --quant_input \
  --calibration_table best_cali_table \
  --processor cv181x \
  --model out/best.cvimodel
```
7. 写 .mud
```
[basic]
type = cvimodel
model = best.cvimodel

[extra]
model_type = yolov11
input_type = rgb
mean = 0, 0, 0
scale = 0.00392156862745098, 0.00392156862745098, 0.00392156862745098
labels = A, B, C, D(和之前 yaml 中的 name 一样)
```