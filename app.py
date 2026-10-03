# coding=utf-8
PRINT_ICON = "🖨️"
SHARE_ICON = "📤"
DELETE_ICON = "🗑️"
import streamlit as st
from google import genai
from PIL import Image
import os
import json
import pandas as pd
from supabase import create_client, Client
import streamlit.components.v1 as components
import html
import base64

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
        
        st.markdown(f"Inloggad som: **{st.session_state['user'].email}**")
        
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

show_menu()

st.divider()

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

flik1, flik2, flik3 = st.tabs(["📷 Skanna Recept", "📚 Mina Recept", "👥 Delade Böcker"])

with flik1:
    st.header("Skanna handskrivet recept")
    
    uppladdad_bild = st.file_uploader(
        "Välj bild på recept...", 
        type=["jpg", "jpeg", "png"], 
        key=f"uploader_{st.session_state['uploader_key']}"
    )
    
    if uppladdad_bild:
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
            
            st.markdown("### 📊 Näringsinnehåll")
            
            naring_data = rec.get("naring", {})
            p_data = naring_data.get("per_portion", {})
            h_data = naring_data.get("per_100g", {})
            
            df_naring = pd.DataFrame({
                "Näringsämne": [
                    "Energi (kcal)", "Protein (g)", "Kolhydrater (g)", 
                    " - varav sockerarter (g)", "Fett (g)", " - varav mättat fett (g)", 
                    "Fiber (g)", "Salt (g)"
                ],
                "Per 100 g": [
                    h_data.get("energi", "-"), h_data.get("protein", "-"), 
                    h_data.get("kolhydrater", "-"), h_data.get("socker", "-"), 
                    h_data.get("fett", "-"), h_data.get("mattat_fett", "-"), 
                    h_data.get("fiber", "-"), h_data.get("salt", "-")
                ],
                "Per portion": [
                    p_data.get("energi", "-"), p_data.get("protein", "-"), 
                    p_data.get("kolhydrater", "-"), p_data.get("socker", "-"), 
                    p_data.get("fett", "-"), p_data.get("mattat_fett", "-"), 
                    p_data.get("fiber", "-"), p_data.get("salt", "-")
                ]
            })
            
            st.table(df_naring)
            
            text_input = st.text_area("Recepttext (Ingredienser & Instruktioner)", value=rec.get("text", ""), height=220)
            
            if st.button("💾 Spara till databasen", key="btn_spara"):
                # FIX: Spara näringsdata som HTML-tabell istället för markdown för att undvika teckenproblem
                def safe_val(data, key):
                    val = data.get(key)
                    if val is None or val == "":
                        return "-"
                    return str(val)
                
                naring_html = f"""
                <h3>📊 Näringsinnehåll</h3>
                <table style="border-collapse: collapse; width: 100%;">
                    <tr style="background-color: #f2f2f2;">
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Näringsämne</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Per 100g</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Per portion</th>
                    </tr>
                    <tr><td style="border: 1px solid #ddd; padding: 8px;">Energi (kcal)</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(h_data, 'energi')}</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(p_data, 'energi')}</td></tr>
                    <tr><td style="border: 1px solid #ddd; padding: 8px;">Protein (g)</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(h_data, 'protein')}</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(p_data, 'protein')}</td></tr>
                    <tr><td style="border: 1px solid #ddd; padding: 8px;">Kolhydrater (g)</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(h_data, 'kolhydrater')}</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(p_data, 'kolhydrater')}</td></tr>
                    <tr><td style="border: 1px solid #ddd; padding: 8px;">&nbsp;&nbsp;- varav sockerarter (g)</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(h_data, 'socker')}</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(p_data, 'socker')}</td></tr>
                    <tr><td style="border: 1px solid #ddd; padding: 8px;">Fett (g)</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(h_data, 'fett')}</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(p_data, 'fett')}</td></tr>
                    <tr><td style="border: 1px solid #ddd; padding: 8px;">&nbsp;&nbsp;- varav mättat fett (g)</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(h_data, 'mattat_fett')}</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(p_data, 'mattat_fett')}</td></tr>
                    <tr><td style="border: 1px solid #ddd; padding: 8px;">Fiber (g)</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(h_data, 'fiber')}</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(p_data, 'fiber')}</td></tr>
                    <tr><td style="border: 1px solid #ddd; padding: 8px;">Salt (g)</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(h_data, 'salt')}</td><td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{safe_val(p_data, 'salt')}</td></tr>
                </table>
                """
                
                full_text = f"{text_input}\n\n{naring_html}"
                
                data_att_spara = {
                    "user_id": st.session_state["user"].id,
                    "titel": titel_input,
                    "kategori": kategori_input,
                    "text": full_text,
                    "is_public": False
                }
                
                try:
                    supabase.table("recept").insert(data_att_spara).execute()
                    st.success("Receptet har sparats!")
                    
                    del st.session_state["analyserat_recept"]
                    st.session_state["uploader_key"] += 1
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Kunde inte spara till Supabase: {e}")

with flik2:
    st.header("Mina sparade recept")
    
    if st.button("🔄 Stäng alla öppna recept"):
        st.rerun()
    
    sokord = st.text_input("🔍 Sök i dina recept...", "", key="sok_recept")
    
    try:
        if sokord:
            res = supabase.table("recept").select("*").eq("user_id", st.session_state["user"].id).ilike("titel", f"%{sokord}%").execute()
        else:
            res = supabase.table("recept").select("*").eq("user_id", st.session_state["user"].id).execute()
        
        recept_lista = res.data
        
        if not recept_lista:
            st.info("Inga sparade recept hittades.")
        else:
            for r in recept_lista:
                titel = r.get("titel") or "Namnlöst recept"
                kategori = r.get("kategori") or "Övrigt"
                recept_id = r.get('id')
                
                with st.expander(f"📌 {titel} ({kategori})"):
                    text_content = r.get("text", "")
                    if text_content is None:
                        text_content = ""
                    elif not isinstance(text_content, str):
                        text_content = str(text_content)
                    
                    # Visa receptet
                    st.markdown(text_content, unsafe_allow_html=True)
                    
                    st.divider()
                    
                    del_text = f"Recept: {titel}\n\n{kategori}\n\n{text_content}"
                    
                    col_share, col_print = st.columns(2)
                    
                    with col_share:
                        share_html = f"""
                        <script>
                        function shareRecipe_{str(recept_id).replace('-', '_')}() {{
                            const shareData = {{
                                title: '{html.escape(titel)}',
                                text: `{del_text.replace('`', '\\`')}`
                            }};
                            
                            if (navigator.share) {{
                                navigator.share(shareData)
                                    .then(() => console.log('Delning lyckades!'))
                                    .catch((error) => console.log('Delning misslyckades:', error));
                            }} else {{
                                navigator.clipboard.writeText(shareData.text).then(() => {{
                                    alert('Receptet har kopierats till urklipp!');
                                }}).catch((err) => {{
                                    console.error('Kunde inte kopiera:', err);
                                }});
                            }}
                        }}
                        </script>
                        
                        <button onclick="shareRecipe_{str(recept_id).replace('-', '_')}()" 
                                style="background-color: #007AFF; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); width: 100%;">
                            {SHARE_ICON} Dela recept
                        </button>
                        """
                        components.html(share_html, height=50)
                    
                    with col_print:
                        # FIX: Använd download_button istället för window.print()
                        print_html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{html.escape(titel)}</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; padding: 20px; background: white; line-height: 1.6; }}
        h1 {{ color: #333; font-size: 28px; margin-bottom: 10px; border-bottom: 2px solid #007AFF; padding-bottom: 10px; }}
        h2 {{ color: #666; font-size: 20px; margin-bottom: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>{html.escape(titel)}</h1>
    <h2>{html.escape(kategori)}</h2>
    <div>{text_content}</div>
    <script>window.onload = function() {{ setTimeout(function() {{ window.print(); }}, 500); }};</script>
</body>
</html>"""
                        
                        st.download_button(
                            label=f"{PRINT_ICON} Ladda ner för utskrift",
                            data=print_html_content.encode('utf-8'),
                            file_name=f"{titel.replace(' ', '_')}_recept.html",
                            mime="text/html",
                            key=f"download_{recept_id}"
                        )
                        st.caption("Öppna filen och välj Skriv ut (Ctrl+P)")
                    
                    if st.button(f"{DELETE_ICON} Radera recept", key=f"del_{recept_id}"):
                        supabase.table("recept").delete().eq("id", recept_id).execute()
                        st.success("Receptet raderades!")
                        st.rerun()
                        
    except Exception as e:
        st.error(f"Kunde inte hämta recept från Supabase: {e}")

with flik3:
    st.header("👥 Delade receptböcker")
    st.markdown("Här kan du välja och läsa andra användares publika receptböcker.")
    
    try:
        publika_res = supabase.table("recept").select("*").eq("is_public", True).execute()
        publika_recept = publika_res.data
        
        if not publika_recept:
            st.info("Inga publika receptböcker hittades just nu.")
        else:
            användare_dict = {}
            for rec in publika_recept:
                uid = rec.get("user_id")
                if uid not in användare_dict:
                    användare_dict[uid] = []
                användare_dict[uid].append(rec)
            
            användar_info = {}
            for uid in användare_dict.keys():
                användar_info[uid] = f"Receptbok ({uid[:8]}...)"
            
            vald_användare = st.selectbox(
                "Välj receptbok:", 
                options=list(användare_dict.keys()),
                format_func=lambda x: användar_info.get(x, f"Receptbok ({x[:8]}...)")
            )
            
            if vald_användare:
                st.divider()
                st.subheader(f"📖 Receptsamling från {användar_info.get(vald_användare, 'Okänd')}")
                
                for r in användare_dict[vald_användare]:
                    titel = r.get("titel") or "Namnlöst recept"
                    kategori = r.get("kategori") or "Övrigt"
                    recept_id = r.get('id')
                    
                    with st.expander(f"📌 {titel} ({kategori})"):
                        text_content = r.get("text", "")
                        if text_content is None:
                            text_content = ""
                        elif not isinstance(text_content, str):
                            text_content = str(text_content)
                            
                        st.markdown(text_content, unsafe_allow_html=True)
                        
                        st.divider()
                        
                        del_text_d = f"Recept: {titel}\n\n{kategori}\n\n{text_content}"
                        
                        col_share_d, col_print_d = st.columns(2)
                        
                        with col_share_d:
                            share_html_d = f"""
                            <script>
                            function shareRecipeD_{str(recept_id).replace('-', '_')}() {{
                                const shareData = {{
                                    title: '{html.escape(titel)}',
                                    text: `{del_text_d.replace('`', '\\`')}`
                                }};
                                
                                if (navigator.share) {{
                                    navigator.share(shareData)
                                        .then(() => console.log('Delning lyckades!'))
                                        .catch((error) => console.log('Delning misslyckades:', error));
                                }} else {{
                                    navigator.clipboard.writeText(shareData.text).then(() => {{
                                        alert('Receptet har kopierats till urklipp!');
                                    }}).catch((err) => {{
                                        console.error('Kunde inte kopiera:', err);
                                    }});
                                }}
                            }}
                            </script>
                            
                            <button onclick="shareRecipeD_{str(recept_id).replace('-', '_')}()" 
                                    style="background-color: #007AFF; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); width: 100%;">
                                {SHARE_ICON} Dela recept
                            </button>
                            """
                            components.html(share_html_d, height=50)
                        
                        with col_print_d:
                            print_html_d = f"""<!DOCTYPE html>
<html>
<head>
    <title>{html.escape(titel)}</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; padding: 20px; background: white; line-height: 1.6; }}
        h1 {{ color: #333; font-size: 28px; margin-bottom: 10px; border-bottom: 2px solid #007AFF; padding-bottom: 10px; }}
        h2 {{ color: #666; font-size: 20px; margin-bottom: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>{html.escape(titel)}</h1>
    <h2>{html.escape(kategori)}</h2>
    <div>{text_content}</div>
    <script>window.onload = function() {{ setTimeout(function() {{ window.print(); }}, 500); }};</script>
</body>
</html>"""
                            
                            st.download_button(
                                label=f"{PRINT_ICON} Ladda ner för utskrift",
                                data=print_html_d.encode('utf-8'),
                                file_name=f"{titel.replace(' ', '_')}_recept.html",
                                mime="text/html",
                                key=f"download_d_{recept_id}"
                            )
                            st.caption("Öppna filen och välj Skriv ut (Ctrl+P)")
                                
    except Exception as e:
        st.error(f"Kunde inte hämta delade recept: {e}")