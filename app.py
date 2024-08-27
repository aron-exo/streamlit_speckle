import streamlit as st
from specklepy.api.client import SpeckleClient
from specklepy.api.credentials import Account

# Access secrets
speckle_token = st.secrets["speckle_token"]
speckle_host = "https://app.speckle.systems/"

# Set up Speckle client
client = SpeckleClient(host=speckle_host)



client.authenticate_with_token(speckle_token)

# Fetch streams
streams = client.stream.list()
stream_names = [stream.name for stream in streams]
stream_dict = {stream.name: stream.id for stream in streams}

st.title("Speckle Viewer in Streamlit")

# Stream selection dropdown
selected_stream = st.selectbox("Select a Stream", stream_names)

if selected_stream:
    stream_id = stream_dict[selected_stream]
    
    # Fetch commits for the selected stream
    commits = client.commit.list(stream_id)
    commit_messages = [commit.message for commit in commits]
    commit_dict = {commit.message: commit.id for commit in commits}
    
    # Commit selection dropdown
    selected_commit = st.selectbox("Select a Commit", commit_messages)
    
    if selected_commit:
        commit_id = commit_dict[selected_commit]
        
        speckle_url = f"https://speckle.xyz/embed?stream={stream_id}&commit={commit_id}"
        
        st.markdown(f"""
        <iframe src="{speckle_url}" width="100%" height="600px" frameborder="0"></iframe>
        """, unsafe_allow_html=True)
