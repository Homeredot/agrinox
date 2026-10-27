# Plant Lens model

Place the trusted FastAI export at `plant_lens_potato_v2.pkl`, or set
`PLANT_LENS_MODEL_PATH` in `.env` to another trusted local file.

Train from authorized Irish-potato images:

```powershell
python -m pip install -r requirements-ml.txt
python scripts/train_plant_lens.py ..\disease_dataset --output models\plant_lens_potato_v2.pkl
```

The supported classes are Irish potato early blight, late blight and healthy,
plus an unsupported-image class sampled from the dataset's pepper and tomato
folders. Low-confidence or closely competing predictions are reported as
uncertain rather than being forced into a disease category.
The trainer reads only the three direct potato class folders, excluding the
duplicate nested disease_dataset tree in this download. It uses a held-out 20%
validation split and writes validation metrics beside the model. Independent
Rwanda field validation is still required.

Train the separate tomato model:

```powershell
python scripts/train_plant_lens.py ..\disease_dataset --crop tomato --per-class-limit 400 --unsupported-limit 1000 --output models\plant_lens_tomato_v1.pkl --version fastai-tomato-disease-dataset-v1
```

The tomato model keeps viruses, late blight, leaf mold, spider-mite stress and
healthy leaves distinct. Visually overlapping bacterial spot, early blight,
Septoria and target spot predictions are presented as a leaf-spot pattern that
requires expert confirmation instead of an image-only definitive diagnosis.

Never load an untrusted `.pkl` file. FastAI `load_learner` uses Python pickle.
