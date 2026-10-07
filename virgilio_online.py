import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from supabase import create_client, Client
from openai import OpenAI
import json
import threading
import os
from flask import Flask

# --- CONFIGURAZIONE SERVER WEB PER RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Virgilio è online e respira!"

def run_server():
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)
# --------------------------------------------

# ==========================================
# 1. CONFIGURAZIONE DELLE CHIAVI API (SICURA)
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# ==========================================
# 2. INIZIALIZZAZIONE DEI CLIENT
# ==========================================
bot = telebot.TeleBot(TELEGRAM_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client_ai = OpenAI(api_key=OPENAI_API_KEY)

print("Virgilio è online e in ascolto su Telegram...")

memoria_conversazioni = {}

# ==========================================
# FUNZIONE DI TRIAGE (Il Segugio Dinamico)
# ==========================================
def classifica_problema(testo, contesto_memoria):
    try:
        scenari_db = supabase.table("scenari_operativi").select("id_scenario, nome_scenario, descrizione_trigger").execute().data
        
        elenco_scenari = ""
        for s in scenari_db:
            elenco_scenari += f"{s['id_scenario']}: {s['nome_scenario']} (Sintomo: {s['descrizione_trigger']})\n"
            
        prompt_triage = f"""
        Sei un classificatore tecnico. Associa il messaggio dell'utente a uno dei seguenti ID scenario.
        
        REGOLE DI MEMORIA STORICA:
        L'utente potrebbe riferirsi a problemi passati. Ecco il suo storico (dal più recente al più vecchio):
        {contesto_memoria}
        
        - Se fa un riferimento ESPLICITO, associalo all'ID corretto.
        - Se fa un riferimento GENERICO, associalo SEMPRE allo scenario dell'interazione PIÙ RECENTE nello storico.
        
        Rispondi SOLO con il numero dell'ID. Se il problema non c'entra NULLA con questi sintomi, rispondi "0".
        
        ELENCO SCENARI:
        {elenco_scenari}
        """
        
        risposta = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_triage},
                {"role": "user", "content": testo}
            ],
            temperature=0.0 
        )
        return int(risposta.choices[0].message.content.strip())
        
    except Exception as e:
        print(f"Errore nel Triage: {e}")
        return 0

# ==========================================
# 3. GESTIONE DEI MESSAGGI IN INGRESSO
# ==========================================
@bot.message_handler(func=lambda message: True)
def gestisci_messaggio(message):
    
    tel_id = message.from_user.id
    nome = message.from_user.first_name
    testo_utente = message.text
    
    # ---------------------------------------------------------
    # FASE A: AUTENTICAZIONE E MEMORIA A LUNGO TERMINE
    # ---------------------------------------------------------
    try:
        risposta = supabase.table("anagrafica_clienti").select("*").eq("telegram_id", tel_id).execute()
        
        if len(risposta.data) > 0:
            dati_utente = risposta.data[0]
        else:
            nuovo_utente = {
                "telegram_id": tel_id,
                "nome": nome,
                "fascia_eta": "Non definita",
                "livello_tech": "Medio",
                "propensione_spesa": "Media",
                "mesi_anzianita": 0,
                "sconto_benvenuto_usato": False  # <-- AGGIUNGIAMO IL JOLLY QUI
            }
            risposta_insert = supabase.table("anagrafica_clienti").insert(nuovo_utente).execute()
            dati_utente = risposta_insert.data[0]
            
        # RECUPERO LONG-TERM MEMORY
        log_db = supabase.table("log_conversazioni").select("riassunto_ia, timestamp_fine").eq("id_cliente", dati_utente['id_cliente']).order("id_log", desc=True).limit(5).execute()
        
        if len(log_db.data) > 0:
            memoria_storica = "\n".join([f"- {log['timestamp_fine'][:10]}: {log['riassunto_ia']}" for log in log_db.data])
        else:
            # FIX AMNESIA: Non scriviamo "è la prima volta", altrimenti ChatGPT si impunta su questa frase.
            memoria_storica = "Nessun ticket di assistenza registrato in precedenza."
            
    except Exception as e:
        print(f"Errore database: {e}")
        return

    # ---------------------------------------------------------
    # FASE B: GENERAZIONE RISPOSTA CON TRIAGE E MEMORIA
    # ---------------------------------------------------------
    try:
        if tel_id not in memoria_conversazioni:
            memoria_conversazioni[tel_id] = {
                "id_scenario_attivo": 0,
                "messaggi_openai": [],
                "upselling_proposto": False # <-- NUOVO CAMPO
            }
        
        if memoria_conversazioni[tel_id]["id_scenario_attivo"] == 0:
            id_rilevato = classifica_problema(testo_utente, memoria_storica)
            if id_rilevato > 0:
                memoria_conversazioni[tel_id]["id_scenario_attivo"] = id_rilevato
                print(f"🎯 [TRIAGE] Problema classificato! ID Scenario: {id_rilevato}")

        id_corrente = memoria_conversazioni[tel_id]["id_scenario_attivo"]
        
        # 3. Costruzione del Prompt Dinamico
        if id_corrente == 0:
            system_prompt = f"""
            IL TUO IDENTIKIT:
            - Il tuo nome è Virgilio. Sei un assistente tecnico di 1° livello.
            - Il cliente con cui stai parlando si chiama {nome}.
            
            STORICO TICKET PREGRESSI (Memoria a Lungo Termine):
            {memoria_storica}
            
            REGOLE TASSATIVE:
            1. IDENTITÀ E TONO: Sei Virgilio. Usa il nome del cliente per metterlo a suo agio. Rispondi in modo naturale e discorsivo. NON ripresentarti in continuazione a ogni messaggio. Se lo storico è vuoto, sii accogliente ma non dire frasi fatte come "è la prima volta che parliamo".
            2. SUPPORTO: Se lamenta un problema tecnico generico o fuori dominio, fai un tentativo di base, poi rassicuralo dicendo che aprirai un Ticket di Livello 2 per un operatore.
            3. INVISIBILITÀ: Non dire MAI di essere un'intelligenza artificiale.
            4. CHIUSURA: Quando capisci che la conversazione generica è giunta al termine (l'utente accetta il ticket, saluta o ringrazia), saluta l'utente e alla fine del tuo messaggio scrivi ESATTAMENTE questa stringa su una riga a sé stante: [FINE_TICKET]
            """
        else:
            scenario = supabase.table("scenari_operativi").select("*").eq("id_scenario", id_corrente).execute().data[0]
            servizio = supabase.table("catalogo_servizi").select("*").eq("id_servizio", scenario['id_servizio_upselling']).execute().data[0]
            
            # FIX DOPPIO ACQUISTO (Anti-fregatura)
            servizi_attivi_cliente = dati_utente.get('servizi_attivi') or []
            ha_gia_comprato = scenario['id_servizio_upselling'] in servizi_attivi_cliente
            
            nome_servizio = servizio['nome_servizio']
            costo_mensile = servizio['costo_mensile']
            domanda_aggancio = servizio['domanda_aggancio']
            vantaggio_db = scenario['vantaggio_competitivo']

            # --- LA TUA REGOLA DEL JOLLY ---
            ha_usato_sconto = dati_utente.get('sconto_benvenuto_usato', False)
            
            # Scenari a pagamento: 1 (Batteria) e 3 (Display)
            if not ha_usato_sconto and id_corrente in [1, 3]:
                regola_sconto = "ATTENZIONE: L'utente non ha mai usato il suo jolly riparazione. Offrigli proattivamente uno sconto di benvenuto del 20% sul prezzo standard."
            else:
                regola_sconto = "Comunica il costo standard senza applicare alcuno sconto."
            # ------------------------------

            if ha_gia_comprato:
                system_prompt = f"""
                Sei Virgilio, assistente virtuale di Customer Care. Stai parlando con {nome}.
                
                STORICO TICKET PREGRESSI:
                {memoria_storica}
                
                CONTESTO DEL PROBLEMA: {scenario['nome_scenario']} (Causa reale: {scenario['diagnosi_tecnica']}).
                ATTENZIONE: L'utente HA GIÀ ACQUISTATO il pacchetto "{nome_servizio}" in passato.
                
                DEVI GUIDARE LA CONVERSAZIONE COSÌ:
                Spiegagli la causa tecnica in modo discorsivo. Subito dopo, RASSICURALO! Digli che, siccome possiede già il pacchetto "{nome_servizio}", il suo problema è interamente coperto e verrà risolto senza costi aggiuntivi o perdite di dati.
                Chiedigli se vuole che avvii le procedure di assistenza gratuita. Se conferma di voler procedere, salutalo e alla fine del tuo messaggio scrivi ESATTAMENTE questa stringa su una riga a sé stante: [FINE_SCENARIO]
                NON FARE NESSUN UPSELLING E NON MOSTRARE MAI I BOTTONI.
                """
            else:
                system_prompt = f"""
                Sei Virgilio, assistente virtuale di Customer Care avanzato. Stai parlando con {nome}.
                Devi essere ESTREMAMENTE naturale, umano ed empatico. È SEVERAMENTE VIETATO usare frasi robotiche. Non dire MAI di essere un'IA.
                
                STORICO INTERAZIONI PREGRESSE (Memoria a Lungo Termine):
                {memoria_storica}
                
                CONTESTO DEL PROBLEMA DELL'UTENTE: {scenario['nome_scenario']} (Causa reale: {scenario['diagnosi_tecnica']}).
                
                REGOLA DI CONGEDO (La Coccola Finale): Non chiudere MAI la conversazione bruscamente se l'utente rifiuta le offerte. Usa il tag [FINE_SCENARIO] SOLO E SOLTANTO quando è l'utente a salutarti, a ringraziarti per congedarsi o a farti capire esplicitamente che non ha più bisogno di te. Fino a quel momento, mantieni viva la conversazione.
                
                REGOLA ANTI-ALLUCINAZIONE (Verità sui Costi): Attieniti ESCLUSIVAMENTE alle informazioni della "soluzione standard". Se la soluzione è gratuita (es. assistenza su impostazioni) e l'utente si lamenta di un prezzo inventato (es. "Perché costa 35 euro?"), DEVI contraddirlo educatamente ma in modo fermo. Spiegagli chiaramente che l'operazione non ha alcun costo e non inventare MAI tecnici, interventi da remoto o prezzi fittizi pur di assecondarlo.

                DEVI GUIDARE LA CONVERSAZIONE SEGUENDO QUESTE 5 FASI LOGICHE.
                REGOLA DI AVANZAMENTO ADATTIVO: Le fasi indicano il percorso, non il numero di messaggi! Puoi scambiare anche 2, 3 o 4 messaggi all'interno della stessa fase se l'utente ha bisogno di sfogarsi, fare domande o capire meglio. 
                Passa alla fase successiva SOLO QUANDO il "Criterio di Sblocco" della fase attuale è stato soddisfatto.

                FASE 1 (Empatia Proattiva): 
                - Obiettivo: Accogliere il problema, calmare l'utente e chiedere il permesso di spiegare la diagnosi.
                - Comportamento: Se l'utente è molto arrabbiato, stagli vicino e rassicuralo per quanti messaggi serve. 
                - CRITERIO DI SBLOCCO PER LA FASE 2: L'utente ti dà esplicitamente il permesso o ti chiede di spiegargli il problema.
                
                FASE 2 (La Mazzata): 
                - Obiettivo: Spiegare la causa tecnica e la soluzione standard: "{scenario['soluzione_standard_costo']}". {regola_sconto}
                - Comportamento: Se l'utente fa domande tecniche ("Ma come si è rotto?", "Perché costa così tanto?"), rispondi ai suoi dubbi rimanendo in questa fase. Non avere fretta.
                - CRITERIO DI SBLOCCO PER LA FASE 3: L'utente ha compreso la diagnosi e il costo, e ti dice cosa ne pensa (es. "Va bene", "Che salasso", "Non so se mi conviene").
                
                FASE 3 (Decisione ed Esplorazione): 
                - Obiettivo: Valutare la sua reazione economica o il disagio per la soluzione manuale.
                - BIVIO A (Rifiuto/Rinvio): Se rinuncia, offri un consiglio gratuito, non proporre servizi e attendi.
                - BIVIO B (Accettazione): Se reputa la soluzione fattibile, formula la domanda esplorativa: "{domanda_aggancio}". NON nominare il pacchetto o il prezzo.
                - CRITERIO DI SBLOCCO PER LA FASE 4: L'utente reagisce alla domanda (con interesse o con un rifiuto netto).
                   
                FASE 4 (Presentazione o Bypass): 
                - Obiettivo: Se ha mostrato interesse, spiegagli che esiste "{nome_servizio}" a SOLO {costo_mensile} € al mese. Usa il vantaggio: "{vantaggio_db}". Chiedigli cosa ne pensa.
                - Comportamento: Rispondi a qualsiasi sua domanda o dubbio sul servizio (es. "Ma c'è il vincolo?", "Come si paga?"). 
                - Bypass: Se aveva declinato l'offerta iniziale, salta subito questa fase.
                - CRITERIO DI SBLOCCO PER LA FASE 5: L'utente prende una decisione finale (accetta il pacchetto o sceglie la via standard).

                FASE 5 (La Chiusura Formalizzata): 
                - Obiettivo: Chiedere di confermare la scelta finale tramite i tasti.
                - Se ha accettato l'abbonamento (Fase 4 completata): Inserisci ESATTAMENTE: [MOSTRA_BOTTONI]
                - Se ha rifiutato (Bypass Fase 4): Inserisci ESATTAMENTE: [MOSTRA_BOTTONE_BASE]
                """
            
        if len(memoria_conversazioni[tel_id]["messaggi_openai"]) == 0:
            memoria_conversazioni[tel_id]["messaggi_openai"].append({"role": "system", "content": system_prompt})
        else:
            memoria_conversazioni[tel_id]["messaggi_openai"][0] = {"role": "system", "content": system_prompt}
            
        memoria_conversazioni[tel_id]["messaggi_openai"].append({"role": "user", "content": testo_utente})
        
        risposta_openai = client_ai.chat.completions.create(
            model="gpt-4o",
            messages=memoria_conversazioni[tel_id]["messaggi_openai"],
            temperature=0.7
        )

        testo_risposta = risposta_openai.choices[0].message.content
        memoria_conversazioni[tel_id]["messaggi_openai"].append({"role": "assistant", "content": testo_risposta})
        
        # GESTIONE DELLE USCITE DALLO SCENARIO
        if "[MOSTRA_BOTTONI]" in testo_risposta:
            memoria_conversazioni[tel_id]["upselling_proposto"] = True # LOGGHIAMO LA PROPOSTA!
            testo_pulito = testo_risposta.replace("[MOSTRA_BOTTONI]", "").strip()
            
            markup = InlineKeyboardMarkup(row_width=1)
            btn_accetta = InlineKeyboardButton("💳 Attiva Abbonamento", callback_data="accetta")
            btn_rifiuta = InlineKeyboardButton("❌ Procedi con Soluzione Standard", callback_data="rifiuta")
            markup.add(btn_accetta, btn_rifiuta)
            
            bot.reply_to(message, testo_pulito, reply_markup=markup)

        elif "[MOSTRA_BOTTONE_BASE]" in testo_risposta:
            memoria_conversazioni[tel_id]["upselling_proposto"] = False # NESSUNA PROPOSTA!
            testo_pulito = testo_risposta.replace("[MOSTRA_BOTTONE_BASE]", "").strip()
            
            # Rendiamo il testo del bottone dinamico in base al contesto (Hardware vs Software)
            id_scenario_corrente = memoria_conversazioni[tel_id].get("id_scenario")
            
            if id_scenario_corrente in [1, 3]:
                testo_bottone = "✅ Conferma Riparazione Standard"
            else:
                testo_bottone = "✅ Procedi con Soluzione Standard"
                
            markup = InlineKeyboardMarkup(row_width=1)
            btn_conferma = InlineKeyboardButton(testo_bottone, callback_data="rifiuta")
            markup.add(btn_conferma)
            
            bot.reply_to(message, testo_pulito, reply_markup=markup)
            
        elif "[FINE_SCENARIO]" in testo_risposta:
            testo_pulito = testo_risposta.replace("[FINE_SCENARIO]", "").strip()
            bot.reply_to(message, testo_pulito)
            threading.Thread(target=salva_ticket_db, args=(tel_id, False, None)).start()
            
        elif "[FINE_TICKET]" in testo_risposta:
            testo_pulito = testo_risposta.replace("[FINE_TICKET]", "").strip()
            bot.reply_to(message, testo_pulito)
            threading.Thread(target=salva_ticket_db, args=(tel_id, False, None)).start()
            
        else:
            bot.reply_to(message, testo_risposta)

    except Exception as e:
        bot.reply_to(message, "Scusa, i miei circuiti sono temporaneamente sovraccarichi. Riprova tra poco!")
        print(f"Errore OpenAI: {e}")

# ==========================================
# FUNZIONE CENTRALIZZATA DI SALVATAGGIO LOG
# ==========================================
def salva_ticket_db(tel_id, upselling_accettato=False, esito_forzato=None):
    memoria = memoria_conversazioni.get(tel_id)
    if not memoria or not memoria["messaggi_openai"]:
        return

    storia_chat = memoria["messaggi_openai"]
    id_scenario = memoria["id_scenario_attivo"]
    upselling_proposto = memoria["upselling_proposto"]
    
    # 1. Calcolo KPI Quantitativi
    # Contiamo solo i messaggi dell'utente per l'Average Turn Count
    numero_scambi = len([m for m in storia_chat if m["role"] == "user"])
    
    # 2. Generazione del Transcript
    transcript_json = json.dumps(storia_chat, ensure_ascii=False)
    
    # 3. Estrazione KPI Qualitativi (LLM in fallback)
    prompt_riassunto = """
    Analizza l'intero ticket di assistenza allegato. Estrai i seguenti dati in formato JSON:
    {
        "riassunto": "Sintesi di max 3 righe",
        "sentiment_iniziale_testo": "Frustrato, Preoccupato, Arrabbiato, Neutro",
        "score_sentiment_iniziale": numero da 1 a 5 (1=Pessimo, 3=Neutro, 5=Ottimo),
        "sentiment_finale_testo": "Soddisfatto, Insoddisfatto, Rassicurato, Neutro, Arrabbiato",
        "score_sentiment_finale": numero da 1 a 5 (1=Pessimo, 3=Neutro, 5=Ottimo),
        "aderenza_tecnica": true/false,
        "esito_commerciale": "Scegli tra: Accettato, Rifiutato, Abbandono"
    }
    REGOLE TASSATIVE PER LA VALUTAZIONE (KPI FALLBACK):
    - 'aderenza_tecnica': imposta a 'false' SE l'assistente sbaglia palesemente la diagnosi iniziale (es. associa un problema di rete/video a scatti a un cambio batteria, o inventa cause inesistenti). Imposta a 'true' SOLO SE il problema lamentato dall'utente corrisponde logicamente alla diagnosi e alla soluzione offerta dal bot.
    - 'esito_commerciale': 
      * Scegli "Accettato" se il cliente accetta la soluzione/preventivo o esegue le istruzioni.
      * Scegli "Rifiutato" se il cliente declina esplicitamente la soluzione perché non gli conviene (chiudendo la chat).
      * Scegli "Abbandono" se interrompe bruscamente per rabbia senza prendere una decisione finale.
    """
    
    risposta_riassunto = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=storia_chat + [{"role": "system", "content": prompt_riassunto}],
        temperature=0.0, 
        response_format={"type": "json_object"}
    )
    
    dati_ia = json.loads(risposta_riassunto.choices[0].message.content)
    
    # 4. Recupero ID Cliente
    dati_utente = supabase.table("anagrafica_clienti").select("id_cliente").eq("telegram_id", tel_id).execute().data[0]
    
    # 5. Insert massivo nel Database
    # Se l'utente ha premuto un bottone, esito_forzato sarà valorizzato (sovrascrivendo il parere dell'LLM).
    esito_finale = esito_forzato if esito_forzato else dati_ia.get("esito_commerciale", "Errore")

    nuovo_log = {
        "id_cliente": dati_utente['id_cliente'],
        "id_scenario": id_scenario,
        "numero_scambi": numero_scambi,
        "sentiment_iniziale": dati_ia.get("sentiment_iniziale_testo", "Neutro"),
        "score_sentiment_iniziale": dati_ia.get("score_sentiment_iniziale", 3),
        "sentiment_finale": dati_ia.get("sentiment_finale_testo", "Neutro"),
        "score_sentiment_finale": dati_ia.get("score_sentiment_finale", 3),
        "aderenza_tecnica": dati_ia.get("aderenza_tecnica", False),
        "esito_commerciale": esito_finale, 
        "upselling_proposto": upselling_proposto,
        "upselling_accettato": upselling_accettato,
        "riassunto_ia": dati_ia.get("riassunto", ""),
        "transcript": transcript_json
    }
    
    supabase.table("log_conversazioni").insert(nuovo_log).execute()
    
    print(f"✅ LOG Salvato a DB! Scambi: {numero_scambi} | Aderenza: {dati_ia.get('aderenza_tecnica')} | Esito: {esito_finale}")

    # 5.5 BRUCIARE IL JOLLY
    # Si brucia SOLO negli scenari hardware a pagamento (1 o 3) 
    # E SOLO SE l'utente ha accettato (tramite bottone o deduzione LLM) il preventivo.
    if id_scenario in [1, 3] and esito_finale == "Accettato":
        supabase.table("anagrafica_clienti").update({"sconto_benvenuto_usato": True}).eq("id_cliente", dati_utente['id_cliente']).execute()
        print("🃏 Jolly Sconto bruciato per questo utente (Riparazione accettata).")
    else:
        print("Il jolly sconto resta intatto (Preventivo rifiutato o scenario gratuito).")
    
    # 6. Pulizia Memoria
    memoria_conversazioni[tel_id] = {"id_scenario_attivo": 0, "messaggi_openai": [], "upselling_proposto": False}
# ==========================================
# 4. GESTIONE BOTTONI E SCRITTURA LOG
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def gestisci_bottoni(call):
    tel_id = call.from_user.id
    esito = call.data 
    
    bot.answer_callback_query(call.id, "Elaborazione ticket in corso...") 
    
    upselling_accettato = True if esito == "accetta" else False
    id_scenario = memoria_conversazioni.get(tel_id, {}).get("id_scenario_attivo", 0)
    
    if id_scenario > 0:
        dati_utente = supabase.table("anagrafica_clienti").select("id_cliente, servizi_attivi").eq("telegram_id", tel_id).execute().data[0]
        scenario = supabase.table("scenari_operativi").select("*").eq("id_scenario", id_scenario).execute().data[0]
        
        if upselling_accettato:
            id_servizio = scenario['id_servizio_upselling']
            servizi_attuali = dati_utente.get('servizi_attivi') or []
            if id_servizio not in servizi_attuali:
                servizi_attuali.append(id_servizio)
                supabase.table("anagrafica_clienti").update({"servizi_attivi": servizi_attuali}).eq("id_cliente", dati_utente['id_cliente']).execute()
            
            testo_ok = scenario['chiusura_upselling_ok'].replace('\\n', '\n')
            testo_finale = f"✅ **Ticket Chiuso**\n\nGrazie per la conferma! 🎉\n{testo_ok}"
        else:
            testo_ko = scenario['chiusura_upselling_ko'].replace('\\n', '\n')
            testo_finale = f"✅ **Ticket Chiuso**\n\nProcediamo con la soluzione standard.\n{testo_ko}"
            
        bot.edit_message_text(
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id, 
            text=testo_finale,
            parse_mode="Markdown"
        )
        
        # Lanciamo il salvataggio log forzando l'esito "Accettato" perché l'utente ha interagito pacificamente con l'UI finale
        threading.Thread(target=salva_ticket_db, args=(tel_id, upselling_accettato, "Accettato")).start()

# ==========================================
# 5. AVVIO DEL LOOP IN ASCOLTO
# ==========================================
if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    
    print("Avvio di Virgilio su Telegram...")
    bot.infinity_polling()