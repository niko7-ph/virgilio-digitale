-- Diamo una pulita prima di creare (l'ordine di drop è inverso alle dipendenze per via delle Foreign Keys)
DROP TABLE IF EXISTS log_conversazioni CASCADE;
DROP TABLE IF EXISTS scenari_operativi CASCADE;
DROP TABLE IF EXISTS catalogo_servizi CASCADE;
DROP TABLE IF EXISTS anagrafica_clienti CASCADE;

-- 1. Tabella Anagrafica Clienti (Allineata alla Tabella 3.1)
CREATE TABLE anagrafica_clienti (
    id_cliente SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    nome VARCHAR(100),
    fascia_eta VARCHAR(50),
    livello_tech VARCHAR(50),
    propensione_spesa VARCHAR(50),
    mesi_anzianita INT DEFAULT 0,
    servizi_attivi INT[] DEFAULT '{}',
    sconto_benvenuto_usato BOOLEAN DEFAULT FALSE
);

-- 2. Tabella Catalogo Servizi (Allineata alla Tabella 3.2 dello screenshot)
CREATE TABLE catalogo_servizi (
    id_servizio SERIAL PRIMARY KEY,
    nome_servizio VARCHAR(100),
    categoria VARCHAR(50),
    costo_mensile DECIMAL(10,2),
    target_tech VARCHAR(50),
    domanda_aggancio TEXT
);

-- 3. Tabella Scenari Operativi (Il Copione statico)
CREATE TABLE scenari_operativi (
    id_scenario SERIAL PRIMARY KEY,
    nome_scenario VARCHAR(100),
    descrizione_trigger TEXT,
    stato_animo_previsto VARCHAR(50),
    diagnosi_tecnica TEXT,
    soluzione_standard_costo TEXT,
    id_servizio_upselling INT REFERENCES catalogo_servizi(id_servizio),
    chiusura_upselling_ok TEXT, 
    chiusura_upselling_ko TEXT,
    vantaggio_competitivo TEXT -- NUOVA COLONNA PER IL PITCH DI VENDITA
);

-- 4. Tabella Log Conversazioni (AGGIORNATA CON NUOVI KPI E SENTIMENT SCORE)
CREATE TABLE log_conversazioni (
    id_log SERIAL PRIMARY KEY,
    id_cliente INT REFERENCES anagrafica_clienti(id_cliente),
    id_scenario INT REFERENCES scenari_operativi(id_scenario),
    timestamp_fine TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    numero_scambi INT,
    sentiment_iniziale VARCHAR(50),
    score_sentiment_iniziale INT,      -- NUOVA COLONNA SCORE SENTIMENT (1-5)
    sentiment_finale VARCHAR(50),
    score_sentiment_finale INT,        -- NUOVA COLONNA SCORE SENTIMENT (1-5)
    aderenza_tecnica BOOLEAN,          -- NUOVA COLONNA KPI TECNICO
    esito_commerciale VARCHAR(50),     -- NUOVA COLONNA KPI COMMERCIALE
    upselling_proposto BOOLEAN,
    upselling_accettato BOOLEAN,
    riassunto_ia TEXT,
    transcript TEXT
);

-- ==========================================
-- INSERIMENTO DATI STATICI (Catalogo e Scenari)
-- ==========================================

-- Popoliamo il Catalogo Servizi
INSERT INTO catalogo_servizi (nome_servizio, categoria, costo_mensile, target_tech, domanda_aggancio) VALUES
(
    'Battery Care Plus', 
    'Hardware', 
    3.99, 
    'Alto',
    'Considerando che i componenti hardware si usurano inevitabilmente, ti sei mai chiesto se esista un modo per smettere di pagare di tasca tua le future sostituzioni fisiche?'
),
(
    'Cloud Storage Premium', 
    'Storage', 
    5.99, 
    'Basso',
    'Visto quanto spazio occupano oggi le app e i video in alta definizione, hai mai pensato a una soluzione automatica per espandere la memoria e mettere al sicuro i tuoi dati senza doverci pensare tu?'
),
(
    'Kasko Full Display', 
    'Hardware', 
    7.99, 
    'Medio',
    'Gli imprevisti purtroppo capitano. Visti i costi medi di una riparazione, ti sei mai chiesto se esista un modo per proteggere il tuo schermo, abbattendo drasticamente le spese per eventuali danni futuri?'
),
(
    'AI Pass Creator', 
    'Software', 
    6.99, 
    'Basso',
    'Visto che il montaggio video manuale richiede tempo e molta pazienza per essere appreso, hai mai pensato all''esistenza di uno strumento guidato dall''Intelligenza Artificiale che applica le modifiche semplicemente ascoltando le tue istruzioni a voce?'
),
(
    'Privacy Shield Pass', 
    'Software', 
    2.99, 
    'Medio',
    'Il tema della privacy è sempre più delicato. Hai mai valutato un servizio di monitoraggio avanzato che ti invia report chiari sull''uso dei permessi in background e ti offre supporto prioritario in caso di dubbi sulla sicurezza?'
);

-- Popoliamo lo Scenario 0
INSERT INTO scenari_operativi (
    id_scenario, nome_scenario, descrizione_trigger, stato_animo_previsto, 
    diagnosi_tecnica, soluzione_standard_costo, id_servizio_upselling, 
    chiusura_upselling_ok, chiusura_upselling_ko, vantaggio_competitivo
) VALUES (
    0, 
    'Fuori Dominio / Richiesta Generica', 
    'L''utente fa una domanda non pertinente o generica.', 
    'Neutro', 
    'Nessuna diagnosi - Fuori Dominio', 
    'N/A', 
    NULL,
    'N/A', 
    'N/A', 
    'N/A'
);

-- Popoliamo gli Scenari Operativi
INSERT INTO scenari_operativi (nome_scenario, descrizione_trigger, stato_animo_previsto, diagnosi_tecnica, soluzione_standard_costo, id_servizio_upselling, chiusura_upselling_ok, chiusura_upselling_ko, vantaggio_competitivo) VALUES
(
    'Deterioramento Batteria', 
    'Drastico calo delle prestazioni energetiche.', 
    'Frustrato', 
    'Usura chimica fisiologica delle celle agli ioni di litio.', 
    'Sostituzione fisica del modulo batteria presso un centro autorizzato. Il costo di listino standard è di 150 euro.',
    1,
    '1️⃣ **Riparazione Attuale:** Riceverai via email le istruzioni per il ritiro tramite corriere e il preventivo (comprensivo dell''eventuale sconto a te riservato).\n2️⃣ **Protezione Futura:** Il servizio "Battery Care Plus" è attivo! Avrai la certezza di sostituzioni coperte per ogni futuro calo fisiologico.',
    'Nessun problema. Riceverai a breve un''email con il preventivo (comprensivo dell''eventuale sconto a te riservato) per la sostituzione della batteria e il link per prenotare il ritiro tramite corriere.',
    'Tutte le future sostituzioni fisiche del modulo batteria saranno coperte dal piano. Niente costi imprevisti o spese di listino fuori garanzia.'
),
(
    'Saturazione Spazio', 
    'Avvisi di sistema: Spazio in esaurimento.', 
    'Ansioso', 
    'Saturazione della memoria di massa (ROM).', 
    'Backup manuale su supporti fisici esterni e successiva cancellazione definitiva di foto, video e applicazioni personali. Richiede tempo e pazienza.',
    2,
    '1️⃣ **Espansione Cloud:** Il tuo pacchetto "Cloud Storage Premium" da 2TB è già attivo sul tuo account.\n2️⃣ **Sincronizzazione:** Apri l''app Impostazioni per avviare il backup automatico e liberare istantaneamente lo spazio.',
    'Il ticket è stato categorizzato. Se deciderai di non espandere la memoria, ti consigliamo di collegare il dispositivo a un PC per un backup manuale dei tuoi dati per non perderli.',
    'Avrai accesso immediato a ben 2TB di spazio di archiviazione per risolvere il problema alla radice, con backup automatico senza che tu debba più cancellare nulla.'
),
(
    'Danno Accidentale Display', 
    'Frantumazione del vetro del display dopo caduta.', 
    'Disperato', 
    'Danno fisico estetico o funzionale al pannello.', 
    'Sostituzione dell''intero blocco display originale. Questo intervento fuori garanzia ha un costo di listino medio stimato di 300 euro.',
    3,
    '1️⃣ **Riparazione Attuale:** Riceverai via email il preventivo per l''incidente odierno (comprensivo dell''eventuale sconto di benvenuto a te riservato) e le istruzioni per il corriere.\n2️⃣ **Protezione Futura:** La tua "Kasko Full Display" è attiva da oggi per proteggerti da futuri imprevisti!',
    'Nessun problema, la tua scelta è assolutamente rispettata. Riceverai a breve un''email con il preventivo, comprensivo dell''eventuale sconto a te riservato, e le indicazioni per spedirci il dispositivo in laboratorio.',
    'Ogni futura sostituzione del pannello rotto per cadute accidentali sarà mitigata dal piano assicurativo. Niente brutte sorprese con i costi di listino.'
),
(
    'Complessità Editing Multimediale', 
    'Richiesta di supporto per fotoritocco o montaggi video complessi.', 
    'Frustrato', 
    'Ostacolo di User Experience (UX) su strumenti tradizionali.', 
    'L''acquisto di licenze per software professionali (spesso costose) e l''investimento di decine di ore in tutorial per apprenderne l''utilizzo manuale.',
    4,
    '1️⃣ **Accesso Premium:** Le funzionalità del pacchetto "AI Pass Creator" sono state sbloccate sul tuo account.\n2️⃣ **Supporto:** Riavvia l''applicazione e troverai un nuovo menù: potrai applicare effetti avanzati semplicemente descrivendoli a voce o per iscritto!',
    'Ti confermiamo che il ticket è chiuso. Per risultati professionali, ti suggeriamo l''esportazione dei file su PC per l''editing manuale con software dedicati.',
    'Non dovrai imparare nessun software complicato: l''Intelligenza Artificiale sposterà l''intero carico di lavoro sul motore generativo integrato, democratizzando di fatto l''accesso all''editing professionale!'
),
(
    'Tracciamento Ambientale', 
    'Accensione spia microfono o fotocamera con app di terze parti.', 
    'Panico', 
    'Tracker attivato da concessione permessi EULA.', 
    'Supporto tecnico gratuito: verifica e revoca manuale degli accessi a fotocamera e microfono dal menu Impostazioni.',
    5,
    '1️⃣ **Pacchetto Acquistato:** Il servizio "Privacy Shield Pass" è stato aggiunto al tuo abbonamento.\n2️⃣ **Attivazione:** Riceverai a breve un''email per attivare la reportistica automatica sui permessi.',
    'Come primo passo, ti raccomandiamo di recarti nel menu Impostazioni > Permessi e revocare manualmente l''accesso a microfono e fotocamera per tutte le app sospette.',
    'Avrai il controllo totale sulla tua sicurezza: riceverai report settimanali dettagliati con i minuti esatti di attivazione dei sensori in background e l''accesso esclusivo a esperti in cybersecurity.'
);