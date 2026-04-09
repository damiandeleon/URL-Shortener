from fastapi import FastAPI

fast = FastAPI()

@fast.get("/")
def read_root():
    return "Hello World"