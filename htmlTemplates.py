css = '''
<style>
:root {
    --page: #f5f9fe;
    --sidebar: #eaf4ff;
    --ink: #21344c;
    --muted: #65758a;
    --line: #d8e6f4;
    --navy: #0c111b;
    --blue: #17466f;
    --blue-soft: #eef6ff;
    --coral: #ff6048;
    --green-bg: #eafff1;
    --green: #14743a;
}

.stApp {
    background: linear-gradient(90deg, var(--sidebar) 0, var(--sidebar) 25.5%, var(--page) 25.5%, var(--page) 100%);
    color: var(--ink);
}

header[data-testid="stHeader"] {
    background: var(--navy) !important;
    border-bottom: 4px solid #f2e48d !important;
    height: 3.4rem !important;
    position: fixed !important;
    left: 0 !important;
    right: 0 !important;
    top: 0 !important;
    z-index: 1002 !important;
}

header[data-testid="stHeader"]::after {
    display: none !important;
}

/* remove header internal strip; sidebar will provide the left top strip */

.block-container {
    max-width: 1480px;
    padding: 4.75rem 1.25rem 3rem 1.1rem;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #eaf4ff 0%, #dfeaf7 100%);
    border-right: 1px solid var(--line);
}

section[data-testid="stSidebar"]::before {
    background: var(--navy);
    border-bottom: 4px solid #f2e48d;
    content: "";
    display: block;
    height: 3.4rem;
    left: 0;
    position: fixed;
    top: 0;
    width: 25.5%;
    z-index: 1003;
}

section[data-testid="stSidebar"] > div {
    padding: 3rem 1rem 2rem 0.3rem;
    position: relative;
    top: -3.1rem;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3:first-of-type {
    margin-left: -0.5rem;
}

section[data-testid="stSidebar"] h3:first-of-type::after {
    margin-left: -0.5rem;
}

section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
    margin-left: -0.5rem;
}

section[data-testid="stSidebar"] h3:first-of-type::after {
    margin-left: -0.3rem;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span {
    color: var(--ink) !important;
}

section[data-testid="stSidebar"] h3:first-of-type {
    font-size: 2rem !important;
    font-weight: 900 !important;
    line-height: 1.2 !important;
    margin: 0 0 1.1rem !important;
}

section[data-testid="stSidebar"] h3:first-of-type::after {
    background: linear-gradient(180deg, #f8fbff 0%, #edf5ff 100%);
    border: 1px solid var(--line);
    border-radius: 14px;
    box-shadow: 0 14px 30px rgba(33, 52, 76, 0.07);
    color: var(--muted);
    content: "Document workspace\\A Upload, process, and review your PDF list from here.";
    display: block;
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.6;
    margin-top: 1rem;
    padding: 1rem 1.1rem;
    white-space: pre-line;
}

section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
    background: var(--navy);
    border: 1px solid #172033;
    border-radius: 7px;
    box-shadow: 0 14px 28px rgba(33, 52, 76, 0.12);
    margin-top: 5.35rem;
    min-height: 145px;
    padding: 1.1rem 1rem 1rem;
    position: relative;
}

section[data-testid="stSidebar"] [data-testid="stFileUploader"]::before {
    color: var(--ink);
    content: "Model: local question-answering model\A\AUpload your PDF here and click on 'Process'";
    display: block;
    font-size: 1.12rem;
    font-weight: 900;
    left: 0;
    line-height: 1.5;
    position: absolute;
    top: -5.25rem;
    white-space: pre-line;
}

section[data-testid="stSidebar"] [data-testid="stFileUploader"] label,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] span,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] p {
    color: #ffffff !important;
    font-size: 1.02rem !important;
    font-weight: 800 !important;
}

section[data-testid="stSidebar"] [data-testid="stFileUploader"] > label {
    display: none !important;
}

section[data-testid="stSidebar"] [data-testid="stFileUploader"] small {
    color: #b8c3d4 !important;
    font-size: 0.92rem !important;
}

section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    align-items: flex-start !important;
    background: transparent !important;
    border: 0 !important;
    display: block !important;
    min-height: 132px !important;
    padding: 0 !important;
    position: relative !important;
}

section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]::before {
    color: #ffffff;
    content: "Drag and drop files here";
    display: block;
    font-size: 1.02rem;
    font-weight: 850;
    left: 0;
    line-height: 1.25;
    margin-bottom: 0.55rem;
    position: absolute;
    top: 0.2rem;
}

section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]::after {
    color: #b8c3d4;
    content: "Limit 200MB per file";
    display: block;
    font-size: 0.92rem;
    font-weight: 700;
    left: 0;
    line-height: 1.25;
    margin-bottom: 0;
    position: absolute;
    top: 2.25rem;
}

section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] [data-testid="stFileUploaderDropzoneInstructions"],
section[data-testid="stSidebar"] [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] {
    display: none !important;
}

section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
    background: #252b36 !important;
    border: 1px solid #4b5565 !important;
    border-radius: 7px !important;
    color: #ffffff !important;
    font-size: 0.98rem !important;
    font-weight: 800 !important;
    left: 0 !important;
    margin-top: 0 !important;
    padding: 0.55rem 0.95rem !important;
    position: absolute !important;
    top: 4.4rem !important;
}

section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button p,
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button span {
    color: #ffffff !important;
    display: inline !important;
    font-size: 0.98rem !important;
    font-weight: 800 !important;
}

section[data-testid="stSidebar"] [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"],
section[data-testid="stSidebar"] [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] span,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] p {
    color: #ffffff !important;
}

.selected-docs,
.summary-box {
    background: #ffffff;
    border: 1px solid var(--line);
    border-radius: 10px;
    color: var(--ink);
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.5;
    margin-top: 1rem;
    padding: 0.9rem 1rem;
}

.selected-doc {
    color: #ffffff;
    font-size: 0.94rem;
    font-weight: 700;
    margin-top: 0.55rem;
    overflow-wrap: anywhere;
}

.processed-box {
    background: var(--green-bg);
    border: 1px solid #62c886;
    border-radius: 10px;
    color: var(--green);
    font-size: 1.03rem;
    font-weight: 900;
    line-height: 1.45;
    margin-top: 1rem;
    padding: 0.9rem 1rem;
}

.processed-box span {
    color: var(--green) !important;
    font-size: 0.92rem;
    font-weight: 800;
}

section[data-testid="stSidebar"] .stButton {
    margin-top: 1.05rem !important;
}

section[data-testid="stSidebar"] .stButton > button {
    background: var(--coral) !important;
    border: 0 !important;
    border-radius: 8px !important;
    box-shadow: 0 10px 22px rgba(255, 96, 72, 0.22);
    color: #ffffff !important;
    font-size: 1.08rem !important;
    font-weight: 850 !important;
    min-width: 108px;
    padding: 0.72rem 1.55rem !important;
}

.block-container h1,
.block-container h2 {
    background: linear-gradient(135deg, var(--blue) 0%, #315f86 58%, #f2afa6 100%);
    border-radius: 18px;
    box-shadow: 0 22px 48px rgba(23, 70, 111, 0.18);
    color: #ffffff !important;
    font-weight: 950 !important;
    margin: 0 0 4.95rem !important;
    min-height: 178px;
    padding: 3.05rem 2.7rem 1.85rem;
    width: 100%;
}

.block-container h1 *,
.block-container h2 * {
    color: #ffffff !important;
    font-weight: 950 !important;
}

.block-container h1::after,
.block-container h2::after {
    color: rgba(255, 255, 255, 0.88);
    content: "Turn static documents into a clean, friendly workspace. Upload PDFs, ask questions naturally, and get quick answers without digging manually.";
    display: block;
    font-size: 1.08rem;
    font-weight: 650;
    line-height: 1.7;
    margin-top: 1.25rem;
    max-width: 920px;
}

.stTextInput {
    background: transparent;
    border: 0;
    margin-top: 0;
    padding: 0;
    position: relative;
}

.stTextInput::before,
.stTextInput label::before,
.stTextInput label::after {
    align-items: center;
    background: linear-gradient(180deg, #f4f9ff 0%, #e9f2fd 100%);
    border: 1px solid var(--line);
    border-radius: 999px;
    box-shadow: 0 8px 18px rgba(33, 52, 76, 0.06);
    color: var(--ink);
    display: flex;
    font-size: 1.02rem;
    font-weight: 900;
    line-height: 1;
    padding: 1rem 1.45rem;
    position: absolute;
    top: -4.35rem;
    white-space: nowrap;
}

.stTextInput::before {
    content: "Upload multiple PDFs";
    left: 0;
}

.stTextInput label::before {
    content: "See the active file name";
    left: 15.2rem;
}

.stTextInput label::after {
    content: "One-click document summary";
    left: 33.6rem;
}

.stTextInput label {
    background: var(--blue-soft);
    border: 1px solid var(--line);
    border-radius: 16px;
    box-shadow: 0 14px 35px rgba(33, 52, 76, 0.06);
    display: block;
    margin-bottom: 2.65rem;
    padding: 1.45rem 1.55rem;
    width: 100%;
}

.stTextInput label p {
    color: transparent !important;
    font-size: 0 !important;
    margin: 0;
}

.stTextInput label p::before {
    color: var(--ink);
    content: "Ask from your document";
    display: block;
    font-size: 1.17rem;
    font-weight: 950;
    line-height: 1.25;
    margin-bottom: 0.65rem;
}

.stTextInput label p::after {
    color: var(--muted);
    content: "Type a question below and the answer will appear in the chat area.";
    display: block;
    font-size: 0.98rem;
    font-weight: 750;
    line-height: 1.45;
}

.stTextInput label + div {
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    display: block !important;
    margin-top: 2.45rem;
    position: relative;
    width: 100%;
}

.stTextInput > div:last-child {
    display: block !important;
    position: relative !important;
    width: 100%;
}

.stTextInput > div:last-child > label {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #65758a !important;
    display: block !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    margin-bottom: 0.75rem !important;
    padding: 0 !important;
    position: relative !important;
    top: auto !important;
}

.stTextInput > div:last-child > label::after {
    display: none !important;
}

.stTextInput > div {
    display: block !important;
    width: 100%;
}

.stTextInput > div > div {
    display: block !important;
    width: 100%;
}

.stTextInput [data-baseweb="input"] {
    align-items: center !important;
    background: #252830 !important;
    border: 2px solid var(--coral) !important;
    border-radius: 8px !important;
    display: flex !important;
    min-height: 3.25rem !important;
    width: 100%;
}

.stTextInput [data-baseweb="input"] input {
    background: #252830 !important;
    border: 0 !important;
    color: #ffffff !important;
    min-height: 3rem !important;
    padding: 0 0.9rem !important;
}

.stTextInput [data-baseweb="input"] input::placeholder {
    color: transparent !important;
}

.stMarkdown, .stText, p, label, span {
    color: var(--ink);
}

.chat-area {
    margin-top: 1.4rem;
}

.summary-display {
    background: #eef6ff;
    border: 1px solid var(--line);
    border-radius: 12px;
    box-shadow: 0 12px 30px rgba(33, 52, 76, 0.08);
    margin-top: 1.4rem;
    padding: 1.5rem;
}

.summary-display h3 {
    color: var(--blue);
    font-weight: 950;
    margin: 0 0 1rem 0;
}

.summary-content {
    color: var(--ink);
    line-height: 1.6;
}

.chat-message {
    align-items: center;
    border: 1px solid var(--line);
    border-radius: 12px;
    box-shadow: 0 12px 30px rgba(33, 52, 76, 0.08);
    display: flex;
    margin-bottom: 1.1rem;
    padding: 1.2rem;
}

.chat-message.user {
    background: #ffffff;
}

.chat-message.bot {
    background: #eef6ff;
}

.chat-message .avatar {
    flex: 0 0 64px;
    width: 64px;
}

.chat-message .avatar img {
    border: 2px solid #ffffff;
    border-radius: 50%;
    box-shadow: 0 8px 18px rgba(33, 52, 76, 0.16);
    max-height: 50px;
    max-width: 50px;
    object-fit: cover;
}

.chat-message .message {
    color: var(--ink);
    line-height: 1.6;
    padding: 0 1rem;
    width: 100%;
}

@media (max-width: 760px) {
    .stApp {
        background: var(--page);
    }

    .block-container {
        padding: 1.4rem 1rem 2rem;
    }

    .block-container h1,
    .block-container h2 {
        border-radius: 14px;
        margin-bottom: 8rem !important;
        min-height: 160px;
        padding: 1.8rem 1.2rem 1.1rem;
    }

    .stTextInput::before,
    .stTextInput label::before,
    .stTextInput label::after {
        border-radius: 14px;
        left: 0;
        padding: 0.8rem 1rem;
        width: calc(100% - 2rem);
    }

    .stTextInput::before {
        top: -7.2rem;
    }

    .stTextInput label::before {
        top: -4.85rem;
    }

    .stTextInput label::after {
        top: -2.5rem;
    }
}
</style>
'''

bot_template = '''
<div class="chat-message bot">
    <div class="avatar">
        <img src="https://cdn-icons-png.flaticon.com/512/6134/6134346.png">
    </div>
    <div class="message">{{MSG}}</div>
</div>
'''

user_template = '''
<div class="chat-message user">
    <div class="message" style="text-align:right">{{MSG}}</div>
    <div class="avatar">
        <img src="https://png.pngtree.com/png-vector/20190321/ourmid/pngtree-vector-users-icon-png-image_856952.jpg">
    </div>
</div>
'''
