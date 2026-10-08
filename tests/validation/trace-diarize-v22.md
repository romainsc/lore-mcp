# Trace diarize-v22 — Comparaison avec référence

## Référence

Fichier: `../ecole/Sources/transcript-reunion-6-oct-2026.md`
Transcription humaine corrigée et validée par Romain.

## Commande

```
preprocess_source(
    file="/tmp/Réunion suivi école sophie 6 octobre 2026.mp3",
    collection="test-diarize-v22",
    enrich="speaker_id",
    speakers="Christine (teacher, speaks English), Sonia (teacher, speaks French), Sarah (parent), Romain (parent)",
    force=true, keep_intermediates=true
)
```

Task: 9d534de5, 3062s (~51 min), file_count: 1.

## Fichiers de sortie

- Résultat: `workspace-validation/build/test-diarize-v22/prep/Réunion suivi école sophie 6 octobre 2026.md`
- Phase1-diarize: `workspace-validation/build/test-diarize-v22/.work/Réunion suivi école sophie 6 octobre 2026.phase1-diarize.md`
- Phase3-enrich: `workspace-validation/build/test-diarize-v22/.work/Réunion suivi école sophie 6 octobre 2026.phase3-enrich.md`
- Stderr log: `/tmp/lore-mcp-stderr.log`

## Problème 1: Attribution speaker incorrecte

| Temps | Référence | v22 |
|-------|-----------|-----|
| 00:00 | **Sonia** : "On en a une arrivée. Allô, vous m'entendez ?" | **Christine** : "We're not going to" |
| 00:02 | **Romain** : "Oui, oui on vous entend, c'est parfait" | **Sonia** : "Hello." |
| 00:04 | **Sonia** : "Par contre on n'entend pas la maman..." | **Sarah** : "Hello? Can you hear me?" |
| 00:07 | **Romain** : "Sarah ?" | **Christine** : (vide) |

Le mapping pyannote SPEAKER_XX → noms est faux. pyannote assigne
des labels arbitraires (SPEAKER_00 à SPEAKER_03). Le speaker_id
enrichment LLM doit les mapper aux noms fournis dans `speakers` hint
en analysant le contenu. Mais le contenu est en anglais (problème 2),
ce qui rend le mapping impossible à faire correctement.

### Cause racine probable

1. pyannote détecte 4 speakers mais les labels (SPEAKER_00-03) ne
   correspondent pas aux personnes réelles
2. Le per-speaker STT transcrit tout en anglais (problème 2)
3. L'enrichissement speaker_id tente de mapper avec le contenu EN
   → impossible de distinguer qui est qui en anglais traduit
4. Le mapping est aléatoire ou basé sur des heuristiques faibles

### Fix nécessaire

Le mapping speaker doit se faire APRÈS la transcription correcte
en langue source. Ou bien utiliser des critères audio (voix, non contenu).

## Problème 2: Tout transcrit en anglais

| Speaker | Langue réelle | Langue v22 | Exemple référence | Exemple v22 |
|---------|--------------|------------|-------------------|-------------|
| Sonia | FR | EN | "On en a une arrivée" | "Hello." |
| Romain | FR | EN | "Oui, oui on vous entend" | "Can you hear me?" |
| Sarah | FR | EN | "Je suis à l'hôpital" | "Hello? Can you hear me?" |
| Christine | EN | EN | "I agree that Sophie..." | "We're not going to" |

Le per-speaker STT (E12.138) appelle transcribe_audio sans hint de
langue. Canary-1B-v2 auto-détecte EN pour tous les speakers.

### Fix nécessaire

- Passer `language` au per-speaker STT basé sur le `speakers` hint
  (Christine→en, Sonia→fr, Sarah→fr, Romain→fr)
- Ou détecter la langue par speaker via le premier segment

## Problème 3: Contenu fragmenté

| Métrique | Référence | v22 |
|----------|-----------|-----|
| Tours de parole | ~100 | 156 |
| Taille moyenne | ~500 chars | 127 chars |
| Sections vides | 0 | 0 |

Le texte est découpé en micro-sections aux limites de mots
(E12.150/E12.151 word boundary split). Chaque turn pyannote
de ~1-2s reçoit un fragment de texte. Les turns courts (0.6s)
produisent des sections de 6-18 chars.

### Fix nécessaire

Fusionner les turns consécutifs du même speaker avant de
distribuer le texte. pyannote produit 342 turns pour 4 speakers
→ beaucoup de turns très courts. Fusionner les turns adjacents
du même speaker réduirait à ~100 turns (proche de la référence).

## Données pipeline (from stderr)

```
pyannote: 342 turns, 4 speakers (SPEAKER_00-03)
  SPEAKER_03: 509s audio
  SPEAKER_02: 241s audio
  SPEAKER_00: 386s audio
  SPEAKER_01: 304s audio

Mapping actuel (incorrect):
  SPEAKER_00 → Christine (devrait être Sonia ou Romain)
  SPEAKER_01 → ?
  SPEAKER_02 → Sonia (devrait être ?)
  SPEAKER_03 → Christine (pyannote split)

Le mapping correct (basé sur la référence):
  Sonia: ~8 min de parole (longues interventions FR)
  Romain: ~6 min (interventions FR)
  Christine: ~5 min (interventions EN)
  Sarah: ~4 min (interventions courtes FR)
```

## Résumé pour correction incrémentale

| Priorité | Fix | Impact |
|----------|-----|--------|
| 1 | **Fusionner turns adjacents** du même speaker avant reconstruction | Réduit 342→~100 sections, paragraphes cohérents |
| 2 | **Langue per-speaker** depuis le `speakers` hint | Transcription FR/EN correcte |
| 3 | **Mapping speaker** après transcription correcte | Attribution correcte |
