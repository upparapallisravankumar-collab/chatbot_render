import streamlit as st
import sqlite3
import json
from datetime import datetime
from openai import OpenAI
import os
from dotenv import load_dotenv

# ========== LOAD ENVIRONMENT VARIABLES ==========
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY not found. Please create a .env file with your key.")

client = OpenAI(api_key=API_KEY)

# ========== DATABASE SETUP ==========
def init_db():
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT,
                    messages TEXT,
                    timestamp TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()

# ========== USER AUTH ==========
def login_user(username, password):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()
    return user

def register_user(username, password):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

# ========== CHAT HISTORY ==========
def save_chat(user_id, title, messages):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("INSERT INTO chats (user_id, title, messages, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, title, json.dumps(messages), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def load_chats(user_id):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT id, title, messages, timestamp FROM chats WHERE user_id=? ORDER BY timestamp DESC", (user_id,))
    chats = c.fetchall()
    conn.close()
    return chats

def delete_chat(chat_id):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("DELETE FROM chats WHERE id=?", (chat_id,))
    conn.commit()
    conn.close()

# ========== UTILITIES ==========
def generate_chat_title(first_message):
    """Generate a meaningful title from the first user message"""
    if not first_message:
        return "New Chat"
    
    # Clean the message and create a title
    message = first_message.strip()
    
    # If message is short, use it as is
    if len(message) <= 30:
        return message
    
    # For longer messages, take first 25 characters and add ellipsis
    return message[:25] + "..."

def get_first_user_message(messages):
    """Extract the first user message"""
    try:
        if isinstance(messages, str):
            messages = json.loads(messages)
        
        for msg in messages:
            if msg.get("role") == "user":
                return msg.get("content", "")
    except:
        pass
    return ""

# ========== MAIN APP ==========
def main():
    st.set_page_config(
        page_title="AI Chatbot with Login", 
        layout="wide",
        page_icon="🤖"
    )
    
    # Custom CSS for better styling
    st.markdown("""
        <style>
        .chat-history-item {
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            cursor: pointer;
        }
        .sidebar .sidebar-content {
            background-color: #f8f9fa;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("🤖 Chatbot with Login & History")

    init_db()

    # --- Session states ---
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "user" not in st.session_state:
        st.session_state.user = None
    if "current_chat_title" not in st.session_state:
        st.session_state.current_chat_title = "New Chat"
    if "show_register" not in st.session_state:
        st.session_state.show_register = False
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = None

    # --- LOGIN / REGISTER FLOW ---
    if not st.session_state.logged_in:
        
        # Show Registration Form if user clicked "Create Account"
        if st.session_state.show_register:
            st.subheader("Create New Account")
            
            # Back to Login button
            if st.button("← Back to Login"):
                st.session_state.show_register = False
                st.rerun()
            
            # Registration Form
            reg_username = st.text_input("Choose Username", key="reg_username")
            reg_password = st.text_input("Choose Password", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
            
            if st.button("Create Account"):
                if not reg_username or not reg_password:
                    st.error("Please fill in all fields")
                elif reg_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(reg_password) < 6:
                    st.error("Password must be at least 6 characters long")
                else:
                    if register_user(reg_username, reg_password):
                        st.success("🎉 Account created successfully! Please login with your credentials.")
                        st.session_state.show_register = False
                        st.rerun()
                    else:
                        st.error("❌ Username already exists. Please choose a different username.")
        
        # Show Login Form by default
        else:
            st.subheader("Login to Your Account")
            
            # Login Form
            login_username = st.text_input("Username", key="login_username")
            login_password = st.text_input("Password", type="password", key="login_password")
            
            if st.button("Login"):
                if not login_username or not login_password:
                    st.error("Please enter both username and password")
                else:
                    user = login_user(login_username, login_password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.session_state.messages = []
                        st.session_state.current_chat_title = "New Chat"
                        st.session_state.current_chat_id = None
                        st.success(f"✅ Welcome back, {login_username}!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")
            
            # Create Account option
            st.markdown("---")
            st.markdown("Don't have an account?")
            if st.button("Create Account", type="secondary"):
                st.session_state.show_register = True
                st.rerun()
        
        return

    # --- MAIN CHAT INTERFACE (after login) ---
    
    # Sidebar Section
    with st.sidebar:
        st.header(f"👋 Welcome, {st.session_state.user[1]}")
        
        # User actions
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🆕 New Chat", use_container_width=True):
                # Save current chat if it has messages
                if st.session_state.messages:
                    # Generate title from first user message
                    first_message = get_first_user_message(st.session_state.messages)
                    chat_title = generate_chat_title(first_message)
                    
                    save_chat(
                        st.session_state.user[0],
                        chat_title,
                        st.session_state.messages
                    )
                # Reset for new chat
                st.session_state.messages = []
                st.session_state.current_chat_title = "New Chat"
                st.session_state.current_chat_id = None
                st.rerun()
        
        with col2:
            if st.button("🚪 Logout", use_container_width=True):
                # Save current chat before logout
                if st.session_state.messages:
                    # Generate title from first user message
                    first_message = get_first_user_message(st.session_state.messages)
                    chat_title = generate_chat_title(first_message)
                    
                    save_chat(
                        st.session_state.user[0],
                        chat_title,
                        st.session_state.messages
                    )
                st.session_state.logged_in = False
                st.session_state.messages = []
                st.session_state.user = None
                st.session_state.current_chat_title = "New Chat"
                st.session_state.current_chat_id = None
                st.rerun()

        # Chat History Section
        st.markdown("---")
        st.subheader("📜 Chat History")
        
        chats = load_chats(st.session_state.user[0])
        
        if chats:
            # Display chat count
            st.caption(f"Total chats: {len(chats)}")
            
            for chat_id, title, messages, timestamp in chats:
                # Use the stored title (which now contains meaningful content)
                display_title = title if title and title != "New Chat" else get_first_user_message(messages)
                if not display_title:
                    display_title = "Empty Chat"
                
                # Create columns for chat item and delete button
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    # Highlight current active chat
                    is_active = st.session_state.current_chat_id == chat_id
                    button_label = f"📍 {display_title}" if is_active else f"💬 {display_title}"
                    
                    if st.button(button_label, key=f"load_{chat_id}", use_container_width=True):
                        st.session_state.messages = json.loads(messages)
                        st.session_state.current_chat_title = title
                        st.session_state.current_chat_id = chat_id
                        st.rerun()
                
                with col2:
                    if st.button("🗑️", key=f"delete_{chat_id}", help="Delete this chat"):
                        delete_chat(chat_id)
                        # If we're deleting the current chat, clear the interface
                        if st.session_state.current_chat_id == chat_id:
                            st.session_state.messages = []
                            st.session_state.current_chat_title = "New Chat"
                            st.session_state.current_chat_id = None
                        st.rerun()
                
                # Show timestamp as caption
                try:
                    chat_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                    st.caption(f"🕒 {chat_time.strftime('%b %d, %H:%M')}")
                except:
                    st.caption("🕒 Unknown time")
                
        else:
            st.info("No previous chats. Start a new conversation!")
            
        # Clear all chats button
        if chats:
            st.markdown("---")
            if st.button("🗑️ Clear All History", type="secondary"):
                for chat_id, _, _, _ in chats:
                    delete_chat(chat_id)
                st.session_state.messages = []
                st.session_state.current_chat_title = "New Chat"
                st.session_state.current_chat_id = None
                st.rerun()

    # --- MAIN CHAT AREA ---
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"💬 {st.session_state.current_chat_title}")
    with col2:
        if st.session_state.messages:
            st.caption(f"Messages: {len(st.session_state.messages)}")

    # Display conversation in a scrollable container
    chat_container = st.container()
    with chat_container:
        if st.session_state.messages:
            for i, msg in enumerate(st.session_state.messages):
                if msg["role"] == "user":
                    st.markdown(f"**🧑 You:** {msg['content']}")
                else:
                    st.markdown(f"**🤖 Bot:** {msg['content']}")
                if i < len(st.session_state.messages) - 1:
                    st.divider()
        else:
            st.info("💡 Start a new conversation by typing a message below!")

    # Input area at bottom
    st.markdown("---")
    col1, col2 = st.columns([4, 1])
    with col1:
        user_input = st.text_input(
            "Type your message...", 
            key="user_input", 
            label_visibility="collapsed",
            placeholder="Ask me anything..."
        )
    with col2:
        send_button = st.button("Send", use_container_width=True, type="primary")

    if send_button and user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Get bot response
        try:
            with st.spinner("🤖 Thinking..."):
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=st.session_state.messages
                )
                bot_reply = response.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": bot_reply})

            # Generate title from first user message if this is a new chat
            if len(st.session_state.messages) == 2:  # First exchange
                first_message = user_input
                st.session_state.current_chat_title = generate_chat_title(first_message)

            # Save or update chat
            save_chat(
                st.session_state.user[0],
                st.session_state.current_chat_title,
                st.session_state.messages
            )
            
            # Reload chats to update the sidebar
            st.rerun()
            
        except Exception as e:
            st.error(f"Error getting response: {str(e)}")

# Run the app
if __name__ == "__main__":
    main()