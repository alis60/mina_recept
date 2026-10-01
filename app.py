import streamlit as st
from google import genai
from PIL import Image
import os
import json
import pandas as pd
from supabase import create_client, Client
import streamlit.components.v1 as components
import html

# --- SUPABASE & GEMINI CONFIG ---
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY"))
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

gemini_api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
client = genai.Client(api_key=gemini_api_key)

# --- MENY-FUNKTION ---
def show_menu():
    with st.sidebar:
        st.markdown("### ⚙️ Inställningar")
        
        # Användarinformation
        st.markdown(f"Inloggad som: **{st.session_state['user'].email}**")
        
        # Delningsinställningar
        st.markdown("#### Delningsinställningar")
        try:
            user_check = supabase.table("recept").select("is_public").eq("user_id", st.session_state["user"].id).execute()
            if user_check.data and len(user_check.data) > 0:
                nuvarande_status = any(r.get("is_public", False) for r in user_check.data)
            else:
                nuvarande_status = False
        except Exception as e:
            st.error(f"Kunde inte läsa delningsstatus: {e}")
            nuvarande_status = False

        gör_publik = st.checkbox("🌍 Gör min receptbok publik", value=nuvarande_status)
        
        if st.button("Uppdatera delningsstatus"):
            try:
                supabase.table("recept").update({"is_public": gör_publik}).eq("user_id", st.session_state["user"].id).execute()
                st.success("Delningsinställningen har sparats!")
                st.rerun()
            except Exception as e:
                st.error(f"Kunde inte uppdatera delningsstatus: {e}")
        
        st.divider()
        
        # Utloggningsknapp
        if st.button("🚪 Logga ut"):
            supabase.auth.sign_out()
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# --- INLOGGNINGSHANTERING ---
if "user" not in st.session_state:
    st.session_state["user"] = None

if not st.session_state["user"]:
    st.title("📖 Receptboken med AI-skanning")
    st.subheader("🔑 Logga in")
    
    with st.form("login_form"):
        email = st.text_input("E-post", key="login_email", autocomplete="email")
        password = st.text_input("Lösenord", type="password", key="login_pass", autocomplete="current-password")
        
        col1, col2 = st.columns(2)
        with col1:
            submit_login = st.form_submit_button("Logga in")
        with col2:
            submit_signup = st.form_submit_button("Skapa konto")
            
        if submit_login:
            try:
                auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state["user"] = auth_res.user
                st.success("Inloggad!")
                st.rerun()
            except Exception as e:
                st.error(f"Fel vid inloggning: {e}")
                
        if submit_signup:
            try:
                auth_res = supabase.auth.sign_up({"email": email, "password": password})
                st.info("Konto skapat! Om e-postbekräftelse krävs, kolla din inkorg.")
            except Exception as e:
                st.error(f"Kunde inte skapa konto: {e}")
                
    st.stop()

# --- HUVUDAPP ---
st.title("📖 Receptboken med AI-skanning")

# Visa meny endast om användaren är inloggad
show_menu()

st.divider()

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

# --- HUVUDAPP (FLIKAR) ---
flik1, flik2, flik3 = st.tabs(["📷 Skanna Recept", "📚 Mina Recept", "👥 Delade Böcker"])

with flik1:
    st.header("Skanna handskrivet recept")
    
    upploadad_bild = st.file_uploader(
        "Välj bild på recept...", 
        type=["jpg", "jpeg", "png"], 
        key=f"uploader_{st.session_state['uploader_key']}"
    )
    
    if upploadad_bild:
        bild = Image.open(uppladdad_bild)
        if bild.size[0] > 1500 or bild.size[1] > 1500:
            bild.thumbnail((1500, 1500))
        st.image(bild, caption="Uppladdad bild (optimerad)", width=300)
        
        if st.button("Analysera recept med AI", key="btn_analysera"):
            with st.spinner("Analyserar handstil och beräknar näringsvärden..."):
                try:
                    prompt = (
                        "Analysera denna bild av ett recept. "
                        "Returnera svaret strikt som en JSON-struktur med följande nycklar:\n"
                        "- 'titel': Receptets namn\n"
                        "- 'kategori': Passande kategori (t.ex. Huvudrätt, Efterrätt, Bakverk)\n"
                        "- 'text': Renskriven version av receptet med ingredienser och instruktioner.\n"
                        "- 'naring': Ett objekt med uppskattade näringsvärden uppdelade i 'per_portion' och 'per_100g'. "
                        "Inkludera nycklarna: 'energi' (kcal/kJ), 'protein' (g), 'kolhydrater' (g), 'socker' (g), "
                        "'fett' (g), 'mattat_fett' (g), 'fiber' (g), 'salt' (g).\n"
                        "Svara ENDAST med giltig JSON utan markdown-kodblock."
                    )
                    
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[bild, prompt]
                    )
                    
                    raw_text = response.text.strip()
                    if raw_text.startswith("```json"):
                        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                    
                    try:
                        recept_data = json.loads(raw_text)
                        st.session_state["analyserat_recept"] = recept_data
                        st.success("Receptet har analyserats!")
                    except json.JSONDecodeError:
                        st.error("Kunde inte tolka AI-svaret. Försök igen med en tydligare bild.")
                    
                except Exception as e:
                    st.error(f"Ett fel uppstod vid anropet till Gemini: {e}")

        if "analyserat_recept" in st.session_state:
            rec = st.session_state["analyserat_recept"]
            
            st.subheader("Granska & Spara")
            
            col_titel, col_kat = st.columns([2, 1])
            with col_titel:
                titel_input = st.text_input("Titel", value=rec.get("titel", ""))
            with col_kat:
                kategori_input = st.text_input("Kategori", value=rec.get("kategori", "Övrigt"))
            
            st.markdown("### 📊