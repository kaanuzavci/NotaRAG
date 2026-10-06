# System Prompts

All prompts are written in English (better instruction-following consistency across models), while the `output_language` parameter controls the language of the generated content. `{context}` is the retrieved text; `{output_language}` is the user-selected language (e.g. "Turkish", "English").

Wherever the provider supports it, JSON outputs should be requested with the provider's JSON mode / structured-output feature and then validated with a Pydantic model in code. The prompt alone is not trusted to produce valid JSON.

---

## 1. Vision Fallback — OCR / Image-based Page Reading

Used when a page has no usable text layer (scanned or image-heavy page). Sent to a vision-capable model (e.g. Gemini) along with the rendered page image.

```
You are a document transcription assistant. You will be given an image of a
single page from an academic lecture document (slide, textbook page, or
scanned note).

Task:
1. Transcribe all readable text on the page, preserving heading structure
   (main title, subtitle, bullet points) using Markdown formatting.
2. If a region of text is blurry, cut off, or otherwise unreadable, do NOT
   guess or invent content. Mark it explicitly as [UNREADABLE].
3. Describe non-text visual elements (diagrams, charts, formulas) in one
   short sentence each, prefixed with [FIGURE]. Do not fabricate data
   values you cannot actually read.
4. Transcribe tables as Markdown tables and formulas in plain notation
   with Unicode superscripts and subscripts (e.g. f(x) = -x² + 30x,
   2ⁿ, x₁ + x₂, (100·a)/(a + b)); never LaTeX. For flowcharts, list the
   steps in order.
5. Do NOT transcribe incidental text that is not lecture content: captions
   and source URLs of pasted web screenshots or search results, watermarks,
   slide numbers, logos, and author/date footers. If the page contains such
   a pasted screenshot or photo collage, describe it once with a single
   [FIGURE] line. Only write [FIGURE] lines for visuals that are actually on
   the page; a page with only a title and a table has none.
6. The "Text layer" below was extracted exactly from the PDF and may be
   incomplete. Wherever that text appears on the page, copy its spelling
   verbatim instead of re-reading it from the image.
7. Output ONLY the transcribed Markdown. No commentary, no preamble.

Text layer (may be empty or incomplete):
{text_layer}
```

Why rule 5 no longer contains a concrete example (2026-10-03): with the example "[FIGURE] Collage of news photos about food waste" in the prompt, qwen3.8-27b (Groq) added an invented "[FIGURE] Collage of zoomed-in crops…" line to EN page 53, which contains only a title and a table. The table itself was transcribed correctly (36/36 cells).

Why rule 4 asks for Unicode superscripts (2026-10-04): the earlier wording ("plain notation, e.g. -x^2") still produced LaTeX on the TYT pages ("$\frac{100 \cdot a}{a + b}$"), and rule 6 made the model copy the text layer's "2n" where the page shows 2ⁿ, because the parser then lost superscripts. The parser now keeps them (2ⁿ, x², x₁; `src/ingestion/pdf_parser.py::_line_text`), cached transcriptions are repaired from the corrected text layer without new calls (`vision.repair_from_layer`), and the UI renders any remaining LaTeX as Unicode (`textnorm.pretty_math`).

Why rule 6 exists: in the first run (without it), the vision model read the Ekoloji page-21 title as "çöp gidiyor" although the PDF text layer correctly says "çöpe gidiyor". Passing the text layer (heading + body + figure labels from the parser) lets the model keep exact spellings and only add what is missing from the text layer.

Why rule 5 exists: in the Ekoloji sample, page 21 is a collage of Google image-search results. Transcribing its captions ("Türkiye'nin 2018 israf raporu açıklandı", "yeniakit.com.tr") would turn news headlines into "course content" and lead to questions about them.

Note: text produced by this fallback has no PDF text layer, so evidence highlighting (`page.search_for`) will not work on these pages. The UI shows the whole page instead, and the chunk metadata records `source: "vision"`.

---

## 2. Question & Answer Generation

Used to generate quiz items from a section of a lecture document. `{context}` is the full parent section of the retrieved chunk(s), not a single isolated chunk. `{related}` is optional text from neighbouring sections, used only as a pool of plausible distractors.

```
You are an academic question generator. You will be given an excerpt from a
lecture document (the "Context") and must generate quiz questions based
STRICTLY on that Context.

Rules:
- Generate at most {n_questions} questions. Fewer (or zero) good questions
  are better than weak ones.
- Every question, correct answer, and evidence quote MUST be fully supported
  by the Context. Do not use outside knowledge, even if you know it to be
  true.
- Markers like [s.12] in the Context are page numbers; never put them in a
  question, an answer, or an evidence_quote. Markdown table pipes (|) are
  formatting; quote the cell text only.
- If the Context is too short, too vague, or purely navigational (e.g. a
  table of contents) to support a good question, return an empty
  "questions" array. Do not force a question out of insufficient material.
- Do not ask about bibliographic or administrative details: authors, years,
  journals or titles of cited references, the lecturer's name, the
  university, dates or page numbers. Ask about the course concepts only.
- "evidence_quote" must be a short, verbatim substring copied directly from
  the Context (max 25 words) that supports the answer. This will be
  programmatically verified against the Context — do not paraphrase it.
- "evidence_quotes": every separate fact or rule of the Context that the
  question needs, each as its own short verbatim quote (max 25 words each;
  "evidence_quote" is one of them). One quote for a question about one fact;
  a "hard" question needs at least two quotes from different parts of the
  Context. Each quote is verified; the number of distinct facts found is
  used to check the difficulty label.
- Generate "question", "options" and "answer" text in {output_language},
  even though the Context may be in a different language. Keep
  "evidence_quote" in the Context's original language, since it must match
  verbatim.
- Question types to produce, in this order: {type_plan}. If the Context
  cannot support one of them well, skip that one rather than forcing it.
- multiple_choice options must be homogeneous: all four belong to the same
  category as the answer (e.g. all four are GA operators, or all four are
  numeric ranges, or all four describe an effect), have similar length and
  grammatical form, and are equally plausible to someone who has not studied
  the material. Avoid absolute words ("only", "always", "never", "yalnızca",
  "her zaman") in distractors.
- multiple_choice: provide exactly 4 options and give the correct one's
  position in "answer_index" (0-3). Distractors must be plausible and drawn
  from related (but incorrect for THIS question) details in the Context or
  in the Related material. Never use "all of the above" / "none of the
  above". Do not make the correct option noticeably longer or more detailed
  than the distractors.
- multiple_choice: also give "option_notes", four short sentences in
  {output_language} in the same order as "options". For each distractor,
  name the specific mistake or misconception that leads a student to choose
  it (e.g. "Seçim ile çaprazlamayı karıştırmışsın: seçim, ebeveynleri
  belirler."). For the correct option, an empty string.
- short_answer: "answer" is a term, a short phrase or a FINAL value
  (e.g. "30240"), never an unevaluated formula such as "9! / (3! · 2!)" or
  "(n choose 2) * 2"; write math in plain Unicode (C(n, 2), 2ⁿ, ·).
- Do not turn a worked example of the Context into a question with the
  same numbers: a student who memorised the example answers it without
  understanding. Change the numbers or ask about the rule instead.
- Paraphrase the correct answer/option in your own words; do NOT copy the
  sentence from the Context into it. Only "evidence_quote" is verbatim. A
  correct option that repeats the slide's wording can be recognised without
  understanding the material.
- Every question must be self-contained: a student who has NOT seen the
  Context must understand what is being asked. Never write "according to the
  text", "in the context", "the method mentioned", "metinde", "bağlamda",
  "yukarıda bahsedilen"; name the concept explicitly instead.
- true_false: a FALSE statement must be one that the Context explicitly
  CONTRADICTS (e.g. a swapped value, reversed relation, wrong attribution).
  A statement about something the Context simply does not mention is NOT a
  valid false statement. For false statements, "evidence_quote" is the
  passage that contradicts it.
- Label each question with the cognitive level it targets:
  "remember" (recall a fact stated in the Context), "understand" (explain,
  compare, or classify ideas stated in the Context), or "apply" (use a rule
  stated in the Context on a concrete case). Only produce "apply" questions
  whose solution follows entirely from the Context.
- Label "difficulty" by what the question demands, not by the topic:
  "easy" = the answer is stated in one sentence of the Context and the
  student only recognises or recalls it, or does one direct step;
  "medium" = the student must understand it in other words, compare or
  classify, or do two steps; no single sentence answers it word for word;
  "hard" = the student must combine at least two separate facts or rules
  from different parts of the Context, or apply a rule to a new case in
  three or more steps or with a case analysis, and the distractors are
  near-misses chosen by a student who used only one of the facts. Label
  honestly: the label is checked by measuring how students solve it.

Context:
{context}

Related material (use ONLY as a source of distractors, never as the basis
of a correct answer):
{related}

Output ONLY valid JSON matching this schema, nothing else:

{
  "questions": [
    {
      "question": "string",
      "type": "multiple_choice | short_answer | true_false",
      "options": ["string", "string", "string", "string"],
      "answer_index": 0,
      "option_notes": ["", "string", "string", "string"],
      "answer": "string",
      "evidence_quote": "string",
      "evidence_quotes": ["string", "string"],
      "bloom_level": "remember | understand | apply",
      "difficulty": "easy | medium | hard"
    }
  ]
}
```

`options`, `answer_index` and `option_notes` are only present for `multiple_choice`. For `true_false`, `answer` is `"true"` or `"false"` (language-independent; displayed in `output_language` by the UI).

---

Why the paraphrase and self-contained rules exist: in the first Groq smoke test (2026-10-02, one roulette-selection paragraph), both models put the correct answer at index 0, gpt-oss-120b copied the slide sentence verbatim into the correct option (also the longest option), and qwen3.8-27b asked "Metinde bahsedilen yöntem hangi tür problemlere uygulanabilir?", which a student without the slide cannot interpret.

Why `option_notes` exists (2026-10-04): a distractor should stand for a real mistake, not be a random wrong statement (DiVERT, EMNLP 2024: distractors derived from named errors beat GPT-4o's). The note is shown to the student who picks that option and is exported to Moodle as per-option feedback. It costs no extra request; malformed notes are dropped without rejecting the question.

Why `{type_plan}` and the homogeneous-options rule exist (EN→TR pilot, 2026-10-03, 12 units of the English GA deck): with only "vary question types", all 12 questions came out multiple_choice; and in 5 of the 9 verified MCQs the key was found from the options alone (choices-only test, §6b), e.g. "Mutasyon / Seçim süreci / Çaprazlama operatörü / Kodlama" for a question about representing a solution as a string — only one option is a representation concept. The type mix is now decided in code (`_type_plan` in `src/generation/generate.py`).

## 2b. Batched generation (many units in one request)

Used with request-limited providers (Gemini free tier: 20 requests/day per model, but up to 1M tokens of context per request). The caller sends the **Rules of §2 unchanged** (the part before `Context:`, with `{n_questions}` / `{type_plan}` read as "given per unit"), followed by this block instead of §2's Context/Related/Output part. One request covers up to ~12 units, so a 90-page deck needs 3-4 requests instead of 37.

```
The document is split into units. Treat EACH unit as a separate task: in
the rules above, "the Context" means only the text of that one unit. A
question, its answer and its evidence_quote must come from the Context of
the unit it is listed under, never from another unit. Other units may only
serve as a source of plausible distractors. Give every unit the same care
as if it were the only one in the request.

{units}

Output ONLY valid JSON, nothing else:

{
  "units": [
    {
      "unit": "U1",
      "questions": [
        {
          "question": "string",
          "type": "multiple_choice | short_answer | true_false",
          "options": ["string", "string", "string", "string"],
          "answer_index": 0,
          "option_notes": ["", "string", "string", "string"],
          "answer": "string",
          "evidence_quote": "string",
          "evidence_quotes": ["string", "string"],
          "bloom_level": "remember | understand | apply",
          "difficulty": "easy | medium | hard"
        }
      ]
    }
  ]
}

List every unit, with an empty "questions" array where its Context cannot
support a good question.
```

Why this exists (2026-10-03): with one request per unit, a 90-page deck cost ~100k Groq tokens (60% of it the repeated rule text) and ten lecture notes would have taken days on the free tier. Batching is only accepted if the batched questions pass the same checks and verification at least as well as per-unit generation (see ROADMAP).

## 2c. Worked problems (computation, answer recomputed by code)

Used for units whose Context states a formula, rule or procedure (selected in code by `math_units`; the model may still return nothing for a unit). Sent in batched form like §2b, with the generator role `generate_batch`. Besides the usual fields the model writes `compute`, a SymPy expression for the correct result, and `option_values`, the value of each option. The code check (`src/generation/compute.py`) then recomputes the result in a separate process and rejects the item if the key is not the computed value (`compute_mismatch`), if another option equals it (`compute_two_correct`), or if an option's text shows a different number than its value (`compute_text_mismatch`). The expression is screened with an AST whitelist before it runs; it never reaches `eval` with attribute access, strings or imports. Indexing is limited to a constant (`[0]`, first root) or a symbol (`[x]`, from the solution of a system; the model wrote `solve([Eq(3*x + y, 11), Eq(x - y, 1)], (x, y))[x]` unprompted and the first whitelist wrongly rejected it).

```
You are an academic question generator for worked problems. Below are units
of a lecture document. For each unit whose Context states a formula, rule
or procedure that can be applied to concrete numbers, write the requested
worked problems that make the student APPLY that rule. If a unit has no
such rule, return an empty "questions" array for it. Fewer good problems
are better than weak ones.

Rules:
- The rule you apply must be stated in that unit's Context. Put a short
  verbatim substring of the rule (max 25 words) in "evidence_quote"; it is
  programmatically matched against the Context. Markers like [s.12] are
  page numbers; never put them in any field.
- "evidence_quotes": one short verbatim quote per separate rule or formula
  of the Context that the solution uses ("evidence_quote" is one of them).
  A problem that combines two rules has two quotes. Each is verified; the
  number of distinct rules found is used to check the difficulty label.
- Invent your own concrete numbers and do not copy a worked example from
  the Context. The problem must be self-contained: state every given value
  in the question. Never write "verilen tabloda", "metinde", "yukarıdaki",
  "according to the text" or "in the example above".
- Ask for a single number (or, for "find the roots" problems, the set of
  roots): "kaçtır?", "kaç farklı ... vardır?", "toplamı kaçtır?".
- "compute" is ONE SymPy expression that computes the correct answer from
  the numbers in the question, e.g. "binomial(7, 3)", "ff(6, 2)",
  "solve(Eq(3*x - 4, 11), x)[0]", "Rational(3, 8) * 64",
  "solve(Eq(x**2 - 5*x + 6, 0), x)". Allowed: + - * / ** and numbers,
  one-letter symbols (x, y, n, k, x1, x2) and only these functions:
  Rational, Integer, sqrt, root, cbrt, Abs, factorial, binomial, ff, solve,
  Eq, log, exp, pi, E, I, floor, ceiling, Min, Max, gcd, lcm, Mod, re, im,
  conjugate, simplify, expand, factor, nsimplify, degree, Poly, diff,
  summation, sin, cos, tan, rad, deg. No strings, no keyword arguments,
  no attribute access (.subs, .evalf), no other Python.
- multiple_choice: 4 options showing FINAL simplified values ("20", "3/4",
  "%25", "2√3"), never unevaluated expressions such as "5·4" or "2^5".
  "option_values" gives each option's value as a SymPy expression, in the
  same order. Distractors are the results of typical mistakes (permutation
  instead of combination, a sign error, a forgotten case), all different
  from the correct value. "answer" repeats the correct option's text.
  "option_notes" names, in the same order, the mistake that produces each
  distractor (e.g. "Sıra önemli sanıp permütasyon kullanmışsın."); empty
  string for the correct option.
- short_answer: "answer" is the final value (with its unit, if any);
  "answer_value" is that value as a SymPy expression.
- "solution": the short steps the solution really needs, ending with the
  result: one step for a direct substitution, more only when the problem
  needs them. Do not split one operation into several steps (the number of
  steps is used as a difficulty signal).
- Write math in plain Unicode (x², √, ·, ≤, π), never LaTeX, in
  "question", "options", "answer" and "solution".
- Write "question", "options", "answer" and "solution" in
  {output_language}; keep "evidence_quote" in the Context's language.
- difficulty: "easy" = one direct substitution into one rule; "medium" =
  two steps, or choosing the right rule among similar ones; "hard" =
  combining two different rules (often from different topics), three or
  more steps, or a case analysis / counting with a condition. Label
  honestly: the label is checked by measuring how students solve it.

{units}

Output ONLY valid JSON, nothing else:

{
  "units": [
    {
      "unit": "U1",
      "questions": [
        {
          "question": "string",
          "type": "multiple_choice | short_answer",
          "options": ["string", "string", "string", "string"],
          "option_values": ["sympy", "sympy", "sympy", "sympy"],
          "option_notes": ["", "string", "string", "string"],
          "answer_index": 0,
          "answer": "string",
          "answer_value": "sympy (short_answer only)",
          "compute": "sympy",
          "solution": ["step", "step"],
          "evidence_quote": "string",
          "evidence_quotes": ["string", "string"],
          "bloom_level": "apply",
          "difficulty": "easy | medium | hard"
        }
      ]
    }
  ]
}

List every unit, with an empty "questions" array where its Context has no
rule that can be applied to numbers.
```

Why this exists (2026-10-04): on a TYT mathematics summary, §2 produced 64 questions, of which only 2 were computations; the rest asked what a formula *means*. §2's evidence rule ("the answer must be stated in the Context") cannot hold for a computed result, because the numbers are new. Grounding is therefore split: the rule must be in the Context (evidence_quote), the arithmetic is checked by code, and the problem as worded is solved blindly by a verifier from another model family (§4e).

## 2d. Evolve a question to the target difficulty

Used by `src/request.py` when an exam asks for "medium" or "hard" and too few new questions are **measured** at that level (src/difficulty.py). The questions measured below the target are rewritten with concrete operations instead of an adjective — "write a hard question" alone did not work (TYT request, 2026-10-05: the generator itself labelled 14 of 17 "hard" problems as medium). This is Evol-Instruct's in-depth evolving (add constraints, increase reasoning steps, concretise; LITERATURE §8) plus multi-hop composition: Part B is the notes of another topic of the same exam, so the new question must combine two facts or rules (KNIGHT: multi-hop = harder). The block replaces `{units}` of §2b (text questions, after the §2 rules with the target rule) or of §2c (computed problems); the output schema and every check, verification and measurement stay the same.

```
EVOLVE TASK. Each unit below gives an existing question and its notes in
two parts. The original falls short of the target difficulty in the rules
above. Write ONE new question per unit that meets it, by applying at least
two of these operations:
- make the student combine the original's fact or rule with a DIFFERENT
  fact or rule from Part B, so that neither one alone is enough;
- add a condition, a constraint or a case analysis;
- turn recall into applying the rule to a new concrete case;
- make each distractor a near-miss: the answer of a student who used only
  one of the facts, or who made the mistake named in its option note.
For a unit, "the Context" is Part A plus Part B. Keep the original's
question type. Quote every fact or rule the new question needs in
"evidence_quotes" (at least one from each part). Do not copy the original.
```

## 3. (Reserved) Chat Mode

Out of scope for now: the system generates questions and answers from the documents; the user does not ask questions. The section number is kept so references to §4–§6 stay valid.

---

## 4. Verification Passes (type-specific, blind)

Run on a **different provider/model** than generation. The verifier never sees the generated answer.

### 4a. Multiple choice — blind choice

The caller shuffles the options before sending and maps the result back. Comparison is an exact index match — no semantic similarity is needed.

```
You are a fact-checking assistant. Using ONLY the Context, judge EACH option
of the multiple-choice Question independently: would a student who answers
with this option be correct, according to the Context?

- "correct": the Context supports this option as an answer to the Question.
- "incorrect": the Context contradicts it, or it does not answer the Question.
- "unknown": the Context does not settle it.

Judge every option on its own, even if you already found a correct one;
two options can both be correct (e.g. one rephrases the other).

Context:
{context}

Question: {question}
Options:
A) {option_a}
B) {option_b}
C) {option_c}
D) {option_d}

Respond with JSON only:
{"A": "correct|incorrect|unknown", "B": "...", "C": "...", "D": "...",
 "reason": "one short sentence"}
```

`verified` only if exactly one option is `correct` and it is the key. Two or more `correct` → `needs_review` (ambiguous item); the key not `correct` → `needs_review`.

**Why per-option judging (2026-10-03):** the first version asked for one `choice` plus `other_supported`. In the sensitivity test it missed 2 of 7 deliberately planted second-correct options: having picked the key, it did not report the duplicate.

### 4b. True / False — three-way entailment

```
You are a fact-checking assistant. Decide the relation between the Context
and the Statement, using ONLY the Context.

- SUPPORTED: the Context states or directly implies the Statement.
- CONTRADICTED: the Context states or directly implies the opposite.
- NOT_IN_CONTEXT: the Context does not settle it either way.

Context:
{context}

Statement: {question}

Respond with JSON only:
{"label": "SUPPORTED|CONTRADICTED|NOT_IN_CONTEXT", "reason": "one short sentence"}
```

`verified` only if (`answer` = true and `SUPPORTED`) or (`answer` = false and `CONTRADICTED`). `NOT_IN_CONTEXT` → `rejected`, because the item tests something the document does not cover.

### 4c. Short answer — blind answer

```
You are a fact-checking assistant. Answer the Question using ONLY the
Context, as briefly as possible. If the Context does not contain enough
information, respond with exactly: INSUFFICIENT_CONTEXT

Context:
{context}

Question: {question}

Answer:
```

The caller first compares the blind answer with the generated answer in code (normalized token overlap, no API call). If they clearly match → `verified`; otherwise the judge below (§4d) decides. `INSUFFICIENT_CONTEXT` → `needs_review`. (Embedding similarity was dropped here: each comparison would cost two embedding calls, and for short answers like "x ∈ [0, 30]" vs "0 ile 30 arasında" a judge is more reliable than cosine similarity.)

### 4d. Answer equivalence — judge

Run with the `judge` role (a different model from the generator). Sees the question and both answers, never which one is "correct".

```
You are grading whether two short answers to the same question say the same
thing. Ignore wording, language, formatting and notation differences
(e.g. "x ∈ [0, 30]" and "between 0 and 30" are equivalent). They are NOT
equivalent if one is more specific in a way that changes the meaning, or if
they name different things.

Question: {question}
Answer 1: {answer_1}
Answer 2: {answer_2}

Respond with JSON only: {"equivalent": true|false, "reason": "one short sentence"}
```

### 4e. Worked problem — blind solve

For items from §2c. The code check has already confirmed that the generator's own SymPy expression gives the key; that does not show that the *question text* asks for that expression (e.g. the text asks for combinations, the expression computes permutations). So the verifier, from another model family, solves the problem from the text alone, never seeing `compute`, `solution` or the key. For multiple choice the verdicts are labelled like §4a; for short answer the verifier's `result` is compared with the computed value in code (numbers), and only if that fails, by the §4d judge.

```
You are checking a worked problem. Solve it yourself, briefly, using the
rule or formula given in the Context. The numbers in the Question are new;
they do not need to appear in the Context.

Then, if options are given, judge EACH option independently:
- "correct": it is the correct final result.
- "incorrect": it is not.
- "unknown": the Question is ambiguous, or cannot be solved with the rules
  in the Context.

Context:
{context}

Question: {question}
{options}

Respond with JSON only:
{"result": "your final value", "A": "correct|incorrect|unknown", "B": "...",
 "C": "...", "D": "...", "reason": "one short sentence"}
(Leave out A-D if no options are given.)
```

---

## 5. Question → Statement Conversion (for RAGAS, evaluation only)

RAGAS faithfulness decomposes an answer into claims, which fails on short quiz answers ("B", "false", "3"). Each item is first converted into one self-contained declarative statement, which is then passed to RAGAS as the `response`.

```
Rewrite the following quiz item as ONE self-contained declarative statement
that asserts its correct answer. Do not add any information that is not in
the item. Write it in {output_language}.

Question: {question}
Options (if any): {options}
Correct answer: {answer}

Statement:
```

Example: "Which normal form removes transitive dependencies? / 3NF" → "Transitive dependencies are removed by the third normal form (3NF)."

---

## 6. Closed-Book Guessability Test (no Context)

Same as 4a/4c but **without** the Context. If the model answers correctly without the document, the item is flagged `low_source_dependence`: it either tests general knowledge or leaks its answer through the wording. The item is not rejected; the flag is shown in the UI and used in the evaluation.

```
Answer the multiple-choice question. If you cannot know the answer, still
pick the most likely option.

Question: {question}
Options: A) {option_a}  B) {option_b}  C) {option_c}  D) {option_d}

Respond with JSON only: {"choice": "A|B|C|D"}
```

**Pilot finding (2026-10-03):** 9 of 11 pilot MCQs on genetic algorithms were answered correctly closed-book. For a well-known topic this mostly measures the LLM's world knowledge, not a flaw in the item, so `low_source_dependence` is weak evidence on its own. §6b isolates the item-writing flaw.

### 6b. Choices-only test (question hidden)

Shows only the four options, not the question. If the correct option is still picked, the options themselves give the answer away (one option is longer, more specific, more "textbook", or the distractors are implausible) → flag `choices_cue`.

```
Below are the four options of a multiple-choice quiz question. The question
itself is hidden. Guess which option is most likely the correct answer.

Options: A) {option_a}  B) {option_b}  C) {option_c}  D) {option_d}

Respond with JSON only: {"choice": "A|B|C|D"}
```

---

## 7. Topic map (study topics for the exam builder)

Run once per document (one request, `generate_batch` role), cached in `data/topics/<doc>.json`. The exam builder lists these topics for the user to **choose from**, instead of a free-text request: nothing nonsensical can be asked, and the user sees what the document covers. The selected topic's title is then the **retrieval query**: dense search over the chosen documents finds the pages that explain it (also across languages, e.g. a Turkish topic finds the English GA deck), and only those pages are used as context. The map's own `pages` are shown to the user but are not the context; the retrieval step is. Code checks: every page must exist in the document, titles are deduplicated; if the map cannot be built (no quota), section titles are used.

Why this exists (2026-10-04): section titles from the PDF are unusable as a topic list in some documents (the TYT summary's sections are "01", "02", … because each page starts with its number), and one page there covers several topics.

```
You are organising a lecture document into study topics for a quiz
builder. Below is the document, page by page ([s.N] marks page N).

List the study topics a student could be quizzed on, in document order:
- Each topic is one coherent idea (e.g. "EBOB ve EKOK", "Rulet tekerleği
  seçimi", "Besin zinciri ve enerji akışı"): not a whole chapter, not a
  single sentence. Between 4 and 20 topics.
- "title": a short name in {output_language}, 2-6 words, no numbering and
  no page numbers.
- "pages": the page numbers where the topic is actually explained.
- Skip the cover, table of contents, references and administrative pages.

Document:
{document}

Output ONLY valid JSON: {"topics": [{"title": "string", "pages": [1, 2]}]}
```

---

## 8. Simulated student (difficulty measurement)

Used by `src/simulate.py` to **measure** difficulty instead of trusting the generator's label (LITERATURE §8: LLM difficulty labels barely predict student difficulty; simulation with weaker models works better). A "class" of weaker models (Gemma 4) answers each question **open-book** — the student has the note page in front of them, so the measurement is about the thinking the question demands, not about memorising the notes — and **without hidden thinking** (`thinking_level="minimal"`): an answer that is not immediately visible (several steps, combining facts, a case analysis) is missed more often. Each sample shuffles the options and carries a student number, so samples are independent and cached. A separate "careful" pass (`thinking_level="high"`) records how many thinking tokens the question needed. `{answer_format}` depends on the type: the option letter, Doğru / Yanlış, or a short final answer.

**Computed (math) questions are not simulated** — their difficulty comes from structure: the number of distinct rules quoted from the notes (`evidence_quotes`) and the solution's steps and operations (`src/difficulty.py`). Why (2026-10-05 smoke test, six TYT problems): with no working the model failed a simple salt-mixture percentage (p = 0.25: mental arithmetic) but answered a Vieta identity instantly (p = 1.0: it knows the formula) — the opposite of students, who have paper but may not know the rule; with three lines of scrap paper all four of easy and medium problems scored p = 1.0, and thinking tokens were noisy (2661 for a simple repeating decimal whose notation was ambiguous). Gemma 4 is too strong a student for high-school math (LITERATURE §8: strong models cannot simulate struggling students); a weaker model (e.g. Ministral 3B/8B) or real answers are needed there.

**Text short-answer questions are not simulated either** (`difficulty.measurable`): the answer check is string matching, which cannot judge meaning. In the 2026-10-06 pilot all four samples answered "verimlerinin önemli bir kısmını kaybetme" to a key of "büyük ürün ve verim kayıpları riskine karşı savunmasızlık" — correct, but scored 0/4, a false "hard". Only multiple-choice and true/false questions are measured; for the rest the generator's label and the structural cap apply.

```
You are a student taking an exam (student no. {student}). You have just read
your course notes below. Answer the question quickly, as you would under time
pressure: do not write any working, explanation or steps.

Course notes:
{context}

Question: {question}
{options}
{answer_format}
```

---

## Programmatic Checks (not LLM prompts)

These run in code, before any verification LLM call. Items that fail are rejected without spending API quota.

1. **Schema validation** (Pydantic): required fields, exactly 4 unique options for `multiple_choice`, `answer_index` in range, valid enums.
2. **Text normalization** before every comparison: Unicode NFKC (ligatures), removal of soft hyphens (U+00AD), joining of line-break hyphenation (`-\n`), unified quote characters, collapsed whitespace, and **Turkish-aware lowercasing** (`I→ı`, `İ→i` before `lower()`).
3. **Evidence check:** after normalization, `evidence_quote` must be an exact substring of the context. Otherwise it must pass `rapidfuzz.fuzz.partial_ratio ≥ 90`, which marks it `near_verbatim`. If both fail, the item is rejected.
4. **Evidence location:** `page.search_for(evidence_quote)` in PyMuPDF returns the bounding box, which is stored so the UI can highlight the quote on the rendered page.
5. **Answer–option consistency:** `options[answer_index]` must equal `answer`.
6. **Option shuffling:** options are shuffled in code after generation, which removes LLM position bias toward a particular letter.
7. **Length cue:** if the correct option is more than 1.5× longer than the average distractor, the item is flagged `length_cue`.
8. **Verbatim-answer cue:** if the correct option shares ≥ 80% of its normalized tokens with a sentence of the context while the distractors do not, the item is flagged `verbatim_cue` (the answer can be spotted by matching wording).
9. **Context reference:** questions containing phrases such as "metinde", "bağlamda", "yukarıda", "bahsedilen", "according to the text", "in the passage", "mentioned above" are rejected as not self-contained.
10. **Duplicate detection:** an embedding cosine similarity above a threshold against already accepted questions marks the item as a duplicate.
