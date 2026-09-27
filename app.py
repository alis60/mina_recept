import streamlit as st
import google.generativeai as genai
from PIL import Image
import os
from supabase import create_client, Client


# --- Konfiguration & Initiering ---
# (Se till att dina secrets är korrekt satta i st.secrets)
# Ändra till detta högst upp i app.py:
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
GEMINI_API_KEY = st.secrets["gemini"]["api_key"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# Konfigurera sidan
st.set_page_config(page_title="Receptbok", page_icon="📖", layout="centered")

# --- CSS för snyggare mobilanpassning (LÄGG IN DETTA HÄR) ---
st.markdown(
    """
    <style>
    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 700px;
    }
    .stAlert {
        word-break: break-word;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Session State för Inloggning & Navigation ---
if "user" not in st.session_state:
    st.session_state.user = None

if "nav_choice" not in st.session_state:
    st.session_state.nav_choice = "Mina recept"

# Enkel inloggningsskärm om ej inloggad
if not st.session_state.user:
    st.subheader("Logga in i Kokboken")
    email = st.text_input("E-post")
    password = st.text_input("Lösenord", type="password")
    if st.button("Logga in"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except Exception as e:
            st.error(f"Inloggningsfel: {e}")
    st.stop()

st.markdown("### 📖 Receptbok")

if st.button("📖 Mina recept", use_container_width=True):
    st.session_state.nav_choice = "Mina recept"

if st.button("➕ Lägg till nytt", use_container_width=True):
    st.session_state.nav_choice = "Lägg till nytt"

if st.button("⚙️ Logga ut", use_container_width=True):
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

st.divider()

# --- VY 1: LÄGG TILL NYTT RECEPT ---
if st.session_state.nav_choice == "Lägg till nytt":
    st.header("Lägg till nytt recept")
    
    uploaded_file = st.file_uploader("Ladda upp bild på receptlapp", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        # Automatiska bildoptimeringar (skala ner till max 1000px bredd för att spara lagring)
        image.thumbnail((1000, 1000))
        st.image(image, caption="Uppladdad bild", use_container_width=True)
        
        if st.button("Analysera recept med Gemini"):
            with st.spinner("Analysera text och näringsinnehåll..."):
                try:
                    model = genai.GenerativeModel('gemini-3.8-flash')
                    prompt = (
                        "Analysera bilden på detta recept. Extrahera följande och svara i ren text (använd inte markdown-block):\n"
                        "1. Receptets namn\n"
                        "2. Ingredienser\n"
                        "3. Instruktioner\n"
                        "4. Uppskattad kategori (t.ex. Huvudrätt, Frukost, Soppa, Bakverk, Efterrätt)\n"
                        "5. Uppskattat näringsinnehåll per portion (kalorier, protein, kolhydrater, fett)"
                    )
                    response = model.generate_content([image, prompt])
                    st.session_state.ai_result = response.text
                except Exception as e:
                    st.error(f"Ett fel uppstod vid analys: {e}")

    if "ai_result" in st.session_state:
        st.subheader("Analysresultat")
        recept_text = st.text_area("Grändskota/redigera texten innan Spara", value=st.session_state.ai_result, height=250)
        
        # Kategorival inför sparande
        kategori = st.selectbox("Kategori", ["Huvudrätt", "Frukost", "Soppa", "Bakverk", "Efterrätt", "Tillbehör", "Övrigt"])
        titel = st.text_input("Receptets titel", value="Mitt nya recept")
        
        if st.button("Spara recept i kokboken"):
            try:
                # Spara till Supabase (utan RLS-krångel om tabellen är öppen eller kopplad till auth.uid())
                data = {
                    "user_id": st.session_state.user.id,
                    "titel": titel,
                    "kategori": kategori,
                    "innehall": recept_text
                }
                supabase.table("recept").insert(data).execute()
                st.success("Receptet sparades framgångsrikt!")
                del st.session_state.ai_result
                st.session_state.nav_choice = "Mina recept"
                st.rerun()
            except Exception as e:
                st.error(f"Kunde inte spara till databasen: {e}")

# --- VY 2: MINA RECEPT ---
elif st.session_state.nav_choice == "Mina recept":
    st.header("Mina sparade recept")
    
    try:
        response = supabase.table("recept").select("*").eq("user_id", st.session_state.user.id).execute()
        recept_lista = response.data
        
        if not recept_lista:
            st.info("Du har inga sparade recept ännu. Klicka på 'Lägg till nytt' för att börja!")
        else:
            # Enkel sök- och filtrering
            sokord = st.text_input("🔍 Sök bland recept", "")
            
            for r in recept_lista:
                if sokord.lower() in r.get("titel", "").lower() or sokord.lower() in r.get("innehall", "").lower():
                    with st.expander(f"📌 {r.get('titel', 'Utan namn')} ({r.get('kategori', 'Övrigt')})"):
                        st.text(r.get("innehall"))
                        if st.button("Radera recept", key=f"del_{r.get('id')}"):
                            supabase.table("recept").delete().eq("id", r.get("id")).execute()
                            st.rerun()
    except Exception as e:
        st.error(f")Kunde inte hämta recept från databasen: {e}")