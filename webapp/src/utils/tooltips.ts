/** Italian descriptions for financial terms shown on hover. */
export const T: Record<string, string> = {
  // Macro
  vix:
    "Indice di volatilità implicita dell'S&P 500. Valori > 30 indicano alta incertezza di mercato, < 15 indicano calma.",
  breadth:
    "Ampiezza di mercato: rapporto tra titoli in rialzo e in ribasso. 'expanding' = slancio diffuso, 'contracting' = vendite generalizzate.",
  yieldCurve:
    "Spread tra rendimento Treasury 10Y e 2Y. Valore negativo (curva invertita) storicamente precede le recessioni.",
  macroScore:
    "Punteggio composito delle condizioni macroeconomiche (0-100). > 55 = favorevole, 40-55 = neutro, < 40 = sfavorevole.",
  macroRegime:
    "Risk-on: gli investitori preferiscono asset rischiosi (azioni). Risk-off: fuga verso asset sicuri (oro, obbligazioni).",

  // Score cards
  benefit:
    "Potenziale di guadagno stimato basato su rendimenti storici, momentum e fondamentali. Scala 0-100: più alto, meglio.",
  risk: "Rischio totale del titolo: volatilità, drawdown massimo e sensibilità al mercato (beta). Scala 0-100: più alto, più rischioso.",
  confidence:
    "Livello di certezza dell'analisi, basato sulla completezza dei dati disponibili. Scala 0-100.",
  composite:
    "Punteggio finale = Beneficio × (1 − Rischio/200). Determina la posizione nella classifica settimanale.",
  newsSentiment:
    "Sentiment delle ultime notizie sul titolo. > 60 = positivo, 40-60 = neutro, < 40 = negativo.",

  // Quant
  beta:
    "Sensibilità del titolo rispetto al mercato. Beta > 1 = più volatile dell'indice, < 1 = più stabile, < 0 = movimento inverso.",
  rsi: "Relative Strength Index (14 periodi). > 70 = ipercomprato (possibile correzione), < 30 = ipervenduto (possibile rimbalzo).",

  // Fundamentals
  fundamentalScore:
    "Punteggio fondamentale composito basato su redditività, valutazione e solidità finanziaria. Scala 0-100.",
  roe: "Return on Equity: utile netto / patrimonio netto. Misura il rendimento generato per gli azionisti. > 15% è considerato buono.",
  pe: "Price/Earnings: prezzo corrente / utile per azione. Indica quante volte gli investitori pagano ogni unità di profitto. Multipli elevati implicano alte aspettative di crescita.",
  pb: "Price/Book: prezzo corrente / valore contabile per azione. < 1 può indicare sottovalutazione rispetto agli asset netti.",
  currentRatio:
    "Attività correnti / passività correnti. > 1.5 = buona liquidità a breve termine; < 1 = possibile tensione di liquidità.",
  quickRatio:
    "Come il Current Ratio ma esclude le scorte. > 1 indica che l'azienda copre i debiti a breve senza liquidare l'inventario.",
  de: "Debt/Equity: debito totale / patrimonio netto. Misura la leva finanziaria. Valori elevati indicano alto indebitamento e maggiore rischio finanziario.",
  eps: "Earnings Per Share: utile netto / numero di azioni in circolazione. Misura la redditività attribuita a ogni singola azione.",
  grahamNumber:
    "Prezzo massimo di acquisto sicuro secondo Benjamin Graham: √(22.5 × EPS × Valore Contabile). Pietra miliare del value investing.",
  marginOfSafety:
    "Scarto tra prezzo corrente e Graham Number. Positivo = il titolo è sotto il valore Graham (potenzialmente conveniente). Negativo = quotato al di sopra.",
  dividendYield:
    "Dividendo annuo / prezzo corrente. Misura il rendimento da cedola del titolo come investimento di reddito.",
  operatingMargin:
    "Profitto operativo / fatturato. Indica l'efficienza operativa dell'azienda: più alto, più redditizia l'attività caratteristica.",
  revenueGrowth:
    "Variazione percentuale dei ricavi anno su anno. Misura il ritmo di espansione del business.",
};
