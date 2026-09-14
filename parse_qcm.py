import csv
import re

SOURCE = "bp_corrected.md"
QUESTIONS_OUT = "questions.csv"
OPTIONS_OUT = "options.csv"

QUESTION_RE = re.compile(r"^(\d+)\.\s+(.*)$")
SCORE_RE = re.compile(r"-?\d+$")

# Source has one genuinely ambiguous option line ("86" for question 259,
# "Pour avancer de 4800 m ... votre finesse-sol est voisine de :"), where a
# purely-numeric option text is concatenated with its score with no
# separator. 4800/600 = 8, so this is text "8" with score 6.
MANUAL_OVERRIDES = {
    "86": ("8", 6),
}


def split_text_score(s):
    if s in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[s]
    m = SCORE_RE.search(s)
    if not m:
        raise ValueError(f"No trailing score found in: {s!r}")
    text = s[: m.start()].strip()
    score = int(m.group())
    return text, score


def main():
    with open(SOURCE, encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    questions = []
    options = []
    current_qid = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        m = QUESTION_RE.match(line)
        if m:
            qid = int(m.group(1))
            text, _score = split_text_score(m.group(2))
            questions.append((qid, text))
            current_qid = qid
        else:
            if current_qid is None:
                raise ValueError(f"Option line found before any question: {line!r}")
            text, score = split_text_score(line)
            options.append((current_qid, text, score))

    with open(QUESTIONS_OUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["questionId", "Text"])
        writer.writerows(questions)

    with open(OPTIONS_OUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["questionId", "text", "score"])
        writer.writerows(options)

    print(f"Questions: {len(questions)}")
    print(f"Options: {len(options)}")

    # Sanity checks
    qids = [q[0] for q in questions]
    expected = list(range(1, len(qids) + 1))
    if qids != expected:
        print("WARNING: question ids are not a clean 1..N sequence")
        for i, (a, b) in enumerate(zip(qids, expected)):
            if a != b:
                print(f"  mismatch at index {i}: got {a}, expected {b}")
                break

    suspicious = [o for o in options if o[1] == "" or o[1][-1].isdigit()]
    if suspicious:
        print(f"WARNING: {len(suspicious)} option(s) with suspicious text:")
        for o in suspicious[:20]:
            print(f"  {o}")

    counts = {}
    for qid, _ in questions:
        counts[qid] = 0
    for qid, _, _ in options:
        counts[qid] = counts.get(qid, 0) + 1
    no_options = [qid for qid, c in counts.items() if c == 0]
    if no_options:
        print(f"WARNING: questions with no options: {no_options}")


if __name__ == "__main__":
    main()
