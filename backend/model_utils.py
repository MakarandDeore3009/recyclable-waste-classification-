import numpy as np
from PIL import Image
import keras

import config

_model = None


def load_model():
    """
    Rebuild the model architecture from the exported config JSON, then
    load the trained weights onto it. This mirrors exactly what your
    original training script had in memory (architecture object +
    weights), just reconstructed from the two saved files.
    """
    global _model
    if _model is None:
        print(f"[model_utils] Rebuilding architecture from {config.MODEL_ARCHITECTURE_PATH} ...")
        with open(config.MODEL_ARCHITECTURE_PATH, "r") as f:
            architecture_json = f.read()
        _model = keras.models.model_from_json(architecture_json)

        print(f"[model_utils] Loading weights from {config.MODEL_WEIGHTS_PATH} ...")
        _model.load_weights(config.MODEL_WEIGHTS_PATH)
        print("[model_utils] Model loaded.")
    return _model


def preprocess_image(pil_image: Image.Image) -> np.ndarray:
    """
    Convert a PIL image into the (1, 224, 224, 3) float32 batch the
    model expects, using whichever preprocessing mode is configured.
    """
    img = pil_image.convert("RGB").resize(config.IMAGE_SIZE)
    arr = np.asarray(img).astype("float32")

    if config.PREPROCESS_MODE == "mobilenet":
        # keras.applications.mobilenet.preprocess_input behavior: scale to [-1, 1]
        arr = (arr / 127.5) - 1.0
    elif config.PREPROCESS_MODE == "rescale":
        arr = arr / 255.0
    else:
        raise ValueError(f"Unknown PREPROCESS_MODE: {config.PREPROCESS_MODE}")

    return np.expand_dims(arr, axis=0)


def predict(pil_image: Image.Image):
    """
    Run inference and return (predicted_class_name, confidence, all_probs_dict).
    """
    model = load_model()
    batch = preprocess_image(pil_image)
    preds = model.predict(batch, verbose=0)[0]  # shape (num_classes,)

    class_names = config.CLASS_NAMES
    if len(preds) != len(class_names):
        raise ValueError(
            f"Model outputs {len(preds)} classes but config.CLASS_NAMES has "
            f"{len(class_names)} entries. Fix config.py."
        )

    top_idx = int(np.argmax(preds))
    predicted_class = class_names[top_idx]
    confidence = float(preds[top_idx])
    all_probs = {class_names[i]: float(preds[i]) for i in range(len(class_names))}

    return predicted_class, confidence, all_probs