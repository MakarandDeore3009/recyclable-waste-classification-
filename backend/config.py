# """
# =====================================================================
#  CONFIG — READ THIS BEFORE RUNNING THE APP
# =====================================================================

# Your model has 3 output classes but we don't know for certain which
# softmax index maps to which real-world label, or which preprocessing
# you used during training. Guessing wrong here means every prediction
# in the app will show the WRONG category.

# STEP 1: Run backend/find_class_order.py (instructions in README.md)
#         with 2-3 sample images you know the true label of. It will
#         print the raw prediction for each preprocessing mode so you
#         can see which index lights up for which image.

# STEP 2: Fill in CLASS_NAMES below in the correct index order
#         (index 0, index 1, index 2 — must match your training
#         folder order, usually alphabetical).

# STEP 3: Set PREPROCESS_MODE to whichever mode gave confident,
#         correct-looking predictions in step 1.

# Until you do this, the app runs with a best-guess default
# (alphabetical order + mobilenet preprocessing) and will show a
# warning banner in the UI reminding you to verify it.
# =====================================================================
# """

# # Index 0, 1, 2 -> must match your training class order exactly.
# # Common ImageDataGenerator/flow_from_directory/image_dataset_from_directory
# # behavior is alphabetical folder order, hence this default guess:
# CLASS_NAMES = ["ewaste", "non_recyclable", "recyclable"]

# # Set this to True once you've confirmed CLASS_NAMES above is correct
# # (via find_class_order.py). Controls the "unverified" warning banner
# # shown in the frontend.
# CLASS_ORDER_VERIFIED = True

# # "mobilenet"  -> keras.applications.mobilenet.preprocess_input (scales to -1..1)
# # "rescale"    -> divide pixel values by 255.0 (scales to 0..1)
# PREPROCESS_MODE = "mobilenet"

# IMAGE_SIZE = (224, 224)

# # Loading directly from the raw architecture JSON + weights.h5 (as
# # originally exported), instead of the combined .keras file.
# MODEL_ARCHITECTURE_PATH = "config.json"
# MODEL_WEIGHTS_PATH = "model.weights.h5"

# # Minimum confidence (0-1) below which the UI will show a
# # "not confident, please retake photo" hint alongside the result.
# LOW_CONFIDENCE_THRESHOLD = 0.55

# # ---------------------------------------------------------------
# # Reward system tuning
# # ---------------------------------------------------------------
# POINTS_PER_SCAN = 10
# POINTS_BONUS_EWASTE = 15       # extra incentive for correctly routing e-waste
# POINTS_DAILY_FIRST_SCAN_BONUS = 5
# POINTS_PER_LEVEL = 100         # points needed per level

# DATABASE_PATH = "waste_app.db"

# UPLOAD_FOLDER = "static/uploads"
# ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
# MAX_UPLOAD_SIZE_MB = 8


# ============================================================
# MODEL CONFIG
# ============================================================

CLASS_NAMES = [
    "recyclable",
    "non_recyclable",
    "e_waste",
]

CLASS_ORDER_VERIFIED = True

IMAGE_SIZE = (224, 224)

MODEL = None
MODEL_PATH = None


# ------------------------------------------------------------
# MODEL FILES
# ------------------------------------------------------------

MODEL_ARCHITECTURE_PATH = (
    BASE_DIR / "model_architecture.json"
)

MODEL_WEIGHTS_PATH = (
    BASE_DIR / "model.weights.h5"
)


# ============================================================
# LOAD MODEL FROM ARCHITECTURE + WEIGHTS
# ============================================================

def load_model_once():

    global MODEL

    if MODEL is not None:
        return MODEL

    try:

        print("[Model] Looking for architecture:")
        print(MODEL_ARCHITECTURE_PATH)

        print("[Model] Looking for weights:")
        print(MODEL_WEIGHTS_PATH)

        # ----------------------------------------------------
        # Check files
        # ----------------------------------------------------

        if not MODEL_ARCHITECTURE_PATH.exists():

            print(
                "[Model] Architecture file NOT FOUND:"
            )

            print(
                MODEL_ARCHITECTURE_PATH
            )

            return None

        if not MODEL_WEIGHTS_PATH.exists():

            print(
                "[Model] Weights file NOT FOUND:"
            )

            print(
                MODEL_WEIGHTS_PATH
            )

            return None

        # ----------------------------------------------------
        # Import TensorFlow
        # ----------------------------------------------------

        from tensorflow.keras.models import model_from_json

        # ----------------------------------------------------
        # Read architecture
        # ----------------------------------------------------

        with open(
            MODEL_ARCHITECTURE_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            architecture_json = file.read()

        # ----------------------------------------------------
        # Rebuild model
        # ----------------------------------------------------

        print(
            "[Model] Rebuilding architecture..."
        )

        MODEL = model_from_json(
            architecture_json
        )

        # ----------------------------------------------------
        # Load trained weights
        # ----------------------------------------------------

        print(
            "[Model] Loading trained weights..."
        )

        MODEL.load_weights(
            MODEL_WEIGHTS_PATH
        )

        # ----------------------------------------------------
        # Compile
        # ----------------------------------------------------

        MODEL.compile(
            optimizer="adam",
            loss="categorical_crossentropy",
            metrics=["accuracy"]
        )

        print(
            "[Model] Loaded successfully!"
        )

        print(
            "[Model] Input shape:",
            MODEL.input_shape
        )

        print(
            "[Model] Output shape:",
            MODEL.output_shape
        )

        return MODEL

    except Exception as exc:

        print(
            "[Model] Failed to load model:"
        )

        print(
            repr(exc)
        )

        import traceback

        traceback.print_exc()

        MODEL = None

        return None
