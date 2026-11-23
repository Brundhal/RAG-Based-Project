import os, sys
sys.path.insert(0, os.getcwd())
import importlib
app = importlib.import_module('app')
st = app.st

# prepare session state
try:
    st.session_state.clear()
except Exception:
    # session_state may not behave like a plain dict when not running Streamlit; fallback to dict
    st.session_state = {}

if isinstance(st.session_state, dict):
    st.session_state['chat_history'] = []
    st.session_state['search_index'] = []
    st.session_state['pdf_data'] = []
    st.session_state['last_error'] = None

sample_text = '''HDFC BANK GROUND FLOOR,NO 1, HAAIRAM AILDAS LAYOUT NEXT TO SHOBHA HOSPITAL.,BENGALURU-560040,KARNATAKA RTGS/ NEFT IFSC : HDFC0004895 Pay Rupees Y Ac No. 50100711268754 Brn: 4895 Pdt:161 SB A/C Account Nurmber Ref. (New Account) Payable at par through cearingtranster at all branches of HOFC BANK LTO 50100711268754 04895-00161-24-00000088 IO000o 2 560 240153: 007 246I 3 CA895 -8-J858 -RTPLO70324 D D M M Y Y Y Y Valld for 3 monthe only Or Bearer Please sgn above gu rRHE À'''

pdf_data = [{
    'name': 'bank pass book.pdf',
    'text': sample_text,
    'has_text': True,
    'metadata': {},
    'page_count': 1,
    'extraction_method': 'text'
}]

st.session_state['pdf_data'] = pdf_data

# Build search index
search_index = app.build_search_index(pdf_data)
print('Built search_index with', len(search_index), 'entries')

question = 'wt is this document about?'
answer = app.answer_from_chunks(question, search_index, pdf_data)
print('Question:', question)
print('Answer:', answer)
print('Last error:', st.session_state.get('last_error'))
