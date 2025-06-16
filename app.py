import streamlit as st
import pandas as pd
import subprocess, platform, shlex
from pathlib import Path
from playwright.sync_api import sync_playwright, Error

# ==========================================================
# Utilitário: abrir Chrome em modo DevTools na porta 9222
# ==========================================================
def abrir_chrome_devtools(url: str, porta: int = 9222) -> None:
    """Tenta abrir o Chrome localmente já com o --remote-debugging-port."""
    sistema = platform.system()

    # Ajuste de caminhos padrão – altere se necessário
    if sistema == "Windows":
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    elif sistema == "Darwin":  # macOS
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    else:  # Linux
        chrome_path = "google-chrome"

    cmd = f'"{chrome_path}" --remote-debugging-port={porta} --new-window {url}'
    try:
        subprocess.Popen(shlex.split(cmd))
        st.success(f"Chrome iniciado em {url} (porta {porta})")
    except FileNotFoundError:
        st.error("Chrome não encontrado no caminho padrão – ajuste a variável `chrome_path` no código.")
    except Exception as e:
        st.error(f"Falha ao abrir o Chrome: {e}")

# ==========================================================
# Função de scraping (a mesma lógica que você já tinha)
# ==========================================================
def coletar_dados(url_cdp: str = "http://localhost:9222") -> pd.DataFrame:
    linhas = []
    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(url_cdp)
            context = browser.contexts[0]
            page = context.pages[-1]

            # Espera a ReactTable
            page.wait_for_selector(".ReactTable", timeout=30_000)
            linhas = page.eval_on_selector_all(
                ".ReactTable .rt-tr-group",
                "nodes => nodes.map(n => "
                "Array.from(n.querySelectorAll('.rt-td')).map(td => td.innerText.trim()))",
            )
    except Error as e:
        st.error(f"Playwright: {e}")
    except IndexError:
        st.error(
            "Nenhuma aba/contexto encontrado – abra o Chrome manualmente "
            "ou use o botão acima para iniciá-lo."
        )
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass

    return pd.DataFrame(linhas)


# ==========================================================
# UI Streamlit
# ==========================================================
st.set_page_config(page_title="Scraper Clínicas Infinity", layout="wide")
st.title("Scraper Clínicas Infinity 🏥")

st.markdown(
    """
Este app coleta dados da **ReactTable** que está aberta no Chrome (modo DevTools, porta 9222),  
gera um DataFrame e permite baixar tudo em Excel.
"""
)

# ---------- BOTÃO: abrir Chrome já no site desejado ----------
if st.button("🔧 Abrir Chrome em DevTools (9222)"):
    abrir_chrome_devtools("https://cs.clinicorp.tech/franchise-info")

st.divider()

# ---------- Endereço CDP (caso use outro host/porta) ----------
url_cdp = st.text_input(
    "Endereço CDP do Chrome",
    value="http://localhost:9222",
    help="Inicie o Chrome com --remote-debugging-port=9222 ou use o botão acima.",
)

# ---------- Coletar dados ----------
if st.button("🚀 Coletar dados da tabela"):
    aviso = st.empty()
    aviso.info("⏳ Coletando…")
    df = coletar_dados(url_cdp)

    if df.empty:
        aviso.error("❌ Nenhuma linha encontrada!")
    else:
        aviso.success(f"✅ {len(df)} linhas coletadas!")
        st.dataframe(df, use_container_width=True)

        # Excel em memória
        xlsx_bytes = df.to_excel(index=False, header=False).encode()
        st.download_button(
            "📥 Baixar Excel",
            xlsx_bytes,
            file_name="clinicas_infinity.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # Log
        st.subheader("Log de processamento")
        total = len(df)
        for i, row in df.iterrows():
            franquia_id = billing_status = ""
            if len(row) == 13:
                franquia_id, billing_status = row[1], row[5]
            elif len(row) == 6:
                franquia_id, billing_status = row[1], row[3]

            if billing_status == "Canceled":
                st.write(f"❌ Franquia **{franquia_id}** CANCELADA. ({i+1}/{total})")
            elif not franquia_id:
                st.write(f"⚠️ Franquia sem ID. ({i+1}/{total})")
            else:
                st.write(f"💾 Salvando franquia **{franquia_id}** ({i+1}/{total})")
