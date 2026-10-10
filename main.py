
import os
import sys
import traceback
from io import StringIO

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodeRequest(BaseModel):
    code: str

class ErrorAnalysis(BaseModel):
    error_lines: list[int]

def execute_python_code(code: str) -> dict:
    old_stdout, old_stderr = sys.stdout, sys.stderr
    stdout, stderr = StringIO(), StringIO()
    sys.stdout, sys.stderr = stdout, stderr

    try:
        exec(code, {})
        return {
            "success": True,
            "output": stdout.getvalue() + stderr.getvalue(),
        }
    except Exception:
        return {
            "success": False,
            "output": traceback.format_exc(),
        }
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr

def analyze_error_with_ai(code: str, error_output: str) -> list[int]:
    client = OpenAI(
        api_key=os.environ["AIPIPE_TOKEN"],
        base_url="https://aipipe.org/openai/v1",
    )

    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{
            "role": "user",
            "content": (
                "Identify the Python source line numbers that caused "
                "the exception. Return only JSON like "
                '{"error_lines":[3]}.\n\n'
                f"CODE:\n{code}\n\nTRACEBACK:\n{error_output}"
            ),
        }],
        response_format={
            "type": "json_object"
        },
    )

    import json
    result = json.loads(response.choices[0].message.content)
    return ErrorAnalysis(**result).error_lines

@app.post("/code-interpreter")
def code_interpreter(request: CodeRequest):
    execution = execute_python_code(request.code)

    if execution["success"]:
        return {"error": [], "result": execution["output"]}

    try:
        lines = analyze_error_with_ai(request.code, execution["output"])
    except Exception:
        lines = []

    return {"error": lines, "result": execution["output"]}

@app.get("/")
def home():
    return {"status": "ok"}