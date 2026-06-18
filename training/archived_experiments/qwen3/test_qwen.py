from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
import torch

BASE_MODEL = "Qwen/Qwen3-4B"

ADAPTER = "../training/outputs/qwen3_4b_hf"

device = "mps" if torch.backends.mps.is_available() else "cpu"

print("Device:", device)

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(
    BASE_MODEL
)

print("Loading base model...")

model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16,
    low_cpu_mem_usage=False
)

print("Moving model to device...")

model = model.to(device)

print("Loading adapter...")

model = PeftModel.from_pretrained(
    model,
    ADAPTER
)

model.eval()

prompt = """
You are a shopping query parser.

Return JSON only.

Query:

Horse riding boots for kids below 3000
"""

inputs = tokenizer(
    prompt,
    return_tensors="pt"
)

inputs = {
    k: v.to(device)
    for k, v in inputs.items()
}

print("Generating...")

outputs = model.generate(
    **inputs,
    max_new_tokens=100
)

print(
    tokenizer.decode(
        outputs[0],
        skip_special_tokens=True
    )
)