import os
import httpx
import gradio as gr

API = os.getenv("API", "http://backend:8000")


# ---------- API Caller Functions ----------
def get_available_sessions():
    try:
        response = httpx.get(f"{API}/sessions", timeout=5.0)
        if response.status_code == 200 and "sessions" in response.json():
            sessions_list = response.json()["sessions"]
            return sessions_list
    except Exception:
        pass
    return ["default"]  # fallback option just in case


def create_session():
    response = httpx.post(f"{API}/session", timeout=10.0)
    response.raise_for_status()
    session_id = response.json()["session_id"]
    return session_id


def get_streaming_response(session_id: str, user_message: str):
    payload = {"session_id": (session_id or "default"), "user_message": user_message}
    try:
        with httpx.Client(timeout=None) as client:
            with client.stream("POST", f"{API}/chat", json=payload) as response:
                response.raise_for_status()
                combined = ""
                for chunk in response.iter_text():
                    combined += chunk
                    yield combined
    except httpx.HTTPStatusError as e:
        error_message = f"[ERROR] Backend returned {e.response.status_code}: {e.response.text}"
        yield error_message
    except Exception as e:
        yield f"[ERROR] Network/client error: {e}"


# ---------- Gradio Helper Functions ----------
def init_sessions():
    sessions = get_available_sessions()
    if not sessions:
        new_session_id = create_session()
        sessions = [new_session_id]
    first_session_id = sessions[0]
    return gr.update(choices=sessions, value=first_session_id), sessions, gr.update(value=[]), ""


def handle_new_chat_click(current_choices):
    new_session_id = create_session()
    sessions = get_available_sessions()
    if new_session_id not in sessions:
        sessions.append(new_session_id)
    return gr.update(choices=sessions, value=new_session_id), sessions, gr.update(value=[]), f"Created: {new_session_id}"


def handle_message_send(current_session_id, user_msg, chat_history):
    current_session_id = (current_session_id or "default").strip()
    user_msg = (user_msg or "").strip()
    if not user_msg:
        yield gr.update()
        return

    # Add user bubble
    chat_history = (chat_history or []) + [[user_msg, ""]]

    # Stream assistant text and update last bubble
    for partial_response in get_streaming_response(current_session_id, user_msg):
        full_response = partial_response
        chat_history[-1][1] = full_response
        yield chat_history


# ---- fetch and map history for a session ----
def load_chat_history(session_id: str):
    session_id = (session_id or "").strip()
    if not session_id:
        return []

    try:
        response = httpx.get(f"{API}/session/{session_id}/history", timeout=10.0)
        response.raise_for_status()
        data = response.json()
        msgs = data.get("messages", [])

        # Convert messages to chat pairs [user_msg, assistant_msg]
        chat_pairs = []
        last_user = None
        for m in msgs:
            role = m.get("role")
            content = m.get("content", "")
            if role == "user":
                last_user = content
            elif role == "assistant":
                chat_pairs.append([last_user or "", content])
                last_user = None
            else:
                pass

        if last_user is not None:
            chat_pairs.append([last_user, ""])

        return chat_pairs

    except Exception as e:
        return []


# ----- Loads the selected session's history into the Chatbot. -----
def handle_session_change(selected_session_id, current_history):
    chat_history_pairs = load_chat_history(selected_session_id)

    if chat_history_pairs:
        status = f"Loaded {len(chat_history_pairs)} turn(s) from session {selected_session_id}."
    else:
        status = f"No history for session {selected_session_id}."
    return gr.update(value=chat_history_pairs), status


def handle_session_deletion(current_session_id, current_choices):
    session_to_be_deleted = (current_session_id or "").strip()
    choices = list(current_choices or [])

    if not session_to_be_deleted:
        return gr.update(), gr.update(), choices, "Select a session first."

    delete_url = f"{API}/session/{session_to_be_deleted}"
    response = httpx.delete(delete_url, timeout=15.0)

    # Remove from dropdown list locally
    choices = [c for c in choices if c != session_to_be_deleted]

    # Create a new chat session if there is no existing chat session after deletion
    if not choices:
        new_sid = create_session()
        choices = [new_sid]
        new_value = new_sid
        status = "Deleted. Started a new chat."
    else:
        new_value = choices[0]
        if response.status_code == 200:
            status = "Deleted."
        else:
            status = f"Delete failed: {response.text}"

    return (
        gr.update(value=[], visible=True),
        gr.update(choices=choices, value=new_value),
        choices,
        status
    )


# ---------- UI ----------
def build_ui():
    CSS = """
    #app-container { max-width: 1400px; margin: 0 auto; }
    #title { text-align: center; margin-bottom: 8px; }
    #sidebar .gr-button, #sidebar .gr-dropdown { margin-bottom: 8px; }
    #chat-area { min-height: 480px; }
    #input-row { gap: 8px; }
    #send-btn button { min-width: 44px; height: 44px; font-size: 18px; }
    #chat-input textarea { height: 44px; }    
    #send-btn button { min-width: 48px; height: 44px; padding: 0 12px; font-size: 18px; }
    """

    with gr.Blocks(title="LLM Chat", css=CSS, elem_id="app-container") as ui:
        gr.Markdown("# LLM Chat", elem_id="title")

        with gr.Row():

            with gr.Column(scale=3, elem_id="sidebar"):
                session_dropdown = gr.Dropdown(
                    label="Session",
                    choices=[],
                    value=None,
                    allow_custom_value=False,
                    interactive=True,
                    scale=2,
                )

                with gr.Row(equal_height=True):
                    new_session_button = gr.Button("New session")
                    delete_session_button = gr.Button("Delete session")

            with gr.Column(scale=10):
                chat = gr.Chatbot(height=520, elem_id="chat-area")

                with gr.Row(equal_height=True, elem_id="input-row"):
                    message_input = gr.Textbox(label="", placeholder="Type and press Enter…", scale=10, elem_id="chat-input")
                    send_button = gr.Button("➤", elem_id="send-btn", scale=0, min_width=48, variant="secondary")
                status = gr.Markdown("")
        choices_state = gr.State([])

        # Init dropdown & clear UI on load
        ui.load(init_sessions, outputs=[session_dropdown, choices_state, chat, status])

        session_dropdown.change(handle_session_change, inputs=[session_dropdown, chat], outputs=[chat, status])

        new_session_button.click(
            fn=handle_new_chat_click,
            inputs=[choices_state],
            outputs=[session_dropdown, choices_state, chat, status]
        )

        send_button.click(
            handle_message_send,
            inputs=[session_dropdown, message_input, chat],
            outputs=[chat],
        )

        # When user press Enter
        message_input.submit(
            handle_message_send,
            inputs=[session_dropdown, message_input, chat],
            outputs=[chat],
        )

        delete_session_button.click(
            fn=handle_session_deletion,
            inputs=[session_dropdown, choices_state],
            outputs=[chat, session_dropdown, choices_state, status]
        )

    return ui


if __name__ == "__main__":
    ui = build_ui()
    ui.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", 7860)), show_api=False)
