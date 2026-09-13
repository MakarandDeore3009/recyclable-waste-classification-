"""
Run this BEFORE using the app for real, to figure out:
  1. Which softmax index corresponds to which real category
  2. Which preprocessing mode (mobilenet vs rescale) your model expects

HOW TO USE
----------
1. Gather 1-3 sample images you know the TRUE label of — ideally one
   clear photo each of a recyclable item, a non-recyclable item, and
   an e-waste item.
2. Run:
       python find_class_order.py path/to/known_recyclable.jpg
       python find_class_order.py path/to/known_ewaste.jpg
       python find_class_order.py path/to/known_non_recyclable.jpg
3. For each image, look at the printed probabilities under BOTH
   preprocessing modes. Whichever mode gives a clear, confident
   probability spike (not a near-uniform ~33/33/33 split) is almost
   certainly your training preprocessing.
4. Note which INDEX lights up for each image you already know the
   label of. That tells you the order to type into config.CLASS_NAMES.
5. Update config.py: set CLASS_NAMES to the correct order, set
   PREPROCESS_MODE to the winning mode, and set CLASS_ORDER_VERIFIED
   = True to remove the warning banner in the app.

If you still have your original training notebook/script, an even
more reliable source of truth: look for a printed
`train_generator.class_indices` (Keras ImageDataGenerator) or
`train_ds.class_names` (tf.keras.utils.image_dataset_from_directory)
in your training logs — that dict/list IS the definitive class order.
"""
import sys
import numpy as np
from PIL import Image
import keras

import config


def run(image_path):
    print(f"\nRebuilding architecture from {config.MODEL_ARCHITECTURE_PATH} ...")
    with open(config.MODEL_ARCHITECTURE_PATH, "r") as f:
        architecture_json = f.read()
    model = keras.models.model_from_json(architecture_json)
    print(f"Loading weights from {config.MODEL_WEIGHTS_PATH} ...")
    model.load_weights(config.MODEL_WEIGHTS_PATH)

    img = Image.open(image_path).convert("RGB").resize(config.IMAGE_SIZE)
    arr = np.asarray(img).astype("float32")

    print(f"\n=== {image_path} ===")
    for mode, transform in [
        ("mobilenet (scale to -1..1)", lambda a: (a / 127.5) - 1.0),
        ("rescale (scale to 0..1)", lambda a: a / 255.0),
    ]:
        batch = np.expand_dims(transform(arr.copy()), axis=0)
        preds = model.predict(batch, verbose=0)[0]
        print(f"\n  Preprocessing = {mode}")
        for i, p in enumerate(preds):
            bar = "#" * int(p * 40)
            print(f"    index {i}: {p:.4f}  {bar}")
        spread = float(np.max(preds) - np.min(preds))
        print(f"    -> confidence spread: {spread:.4f} "
              f"({'looks confident' if spread > 0.3 else 'looks uncertain / maybe wrong mode'})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python find_class_order.py path/to/image.jpg")
        sys.exit(1)
    run(sys.argv[1])