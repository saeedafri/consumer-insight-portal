"""Downloads Ask Coresight's search model at image build (deploy/Dockerfile) and once on a developer's machine:
BAAI's bge-small-en-v1.5 as Qdrant's int8 ONNX export (MIT licence, 67 MB), which api/ask_model.py embed() runs on our
own CPU: 3 ms a question, no call to OpenAI, no cost. The revision is pinned, so every build gets the same model.
A failed download never fails the build: Ask then searches by words alone, and the model reads every question.
    python deploy/ask-model-download.py models/bge-small-en-v1.5"""
import os
import shutil
import sys
import urllib.request

target = sys.argv[1]
SOURCE = "https://huggingface.co/Qdrant/bge-small-en-v1.5-onnx-Q/resolve/aa8f8b060edb00e03bfdd08813a2949946c8ba55"
os.makedirs(target, exist_ok=True)
for name in ("tokenizer.json", "model_optimized.onnx"):
    path = os.path.join(target, name)
    try:
        with urllib.request.urlopen(f"{SOURCE}/{name}", timeout=300) as answer, open(path + ".part", "wb") as out:
            shutil.copyfileobj(answer, out)
        os.replace(path + ".part", path)   # whole files only: a broken download leaves no half file
        print(f"ask-model-download: {name}")
    except OSError as problem:
        print(f"ask-model-download: {name} not downloaded ({problem})")
