"""Gradio chat UI — pure HTTP client of the FastAPI backend.

Placeholder for milestone M0 so the ui image builds; the full Blocks UI
(login, streaming chat, citations) lands in milestone M7.
"""

import os

import gradio as gr

API_URL = os.environ.get("API_URL", "http://localhost:8000")


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Opkey Procurement Assistant") as demo:
        gr.Markdown(f"# Opkey Procurement Assistant\nBackend: `{API_URL}` — UI under construction.")
    return demo


if __name__ == "__main__":
    build_app().launch(server_name="0.0.0.0", server_port=int(os.environ.get("UI_PORT", "7860")))
