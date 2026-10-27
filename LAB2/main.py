import time

rules = [
    {
        "id": "R1",
        "conditions": ["A", "B"],
        "conclusion": "C"
    },
    {
        "id": "R2",
        "conditions": ["B"],
        "conclusion": "D"
    },
    {
        "id": "R3",
        "conditions": ["C"],
        "conclusion": "E"
    }
]


def matches(condition, wm):
    if condition.startswith("NOT "):
        return condition[4:] not in wm
    return condition in wm


def conflict_set(rules, wm):
    result = []

    for rule in rules:
        if all(matches(c, wm) for c in rule["conditions"]):
            if rule["conclusion"] not in wm:
                result.append(rule["id"])

    return result


print("EXERCISE 1")
print("------------")

wm = set()

print("WM:", wm)
print("Conflict Set:", conflict_set(rules, wm))

wm.add("A")

print("\nWM:", wm)
print("Conflict Set:", conflict_set(rules, wm))

wm.add("B")

print("\nWM:", wm)
print("Conflict Set:", conflict_set(rules, wm))

wm.add("C")

print("\nWM:", wm)
print("Conflict Set:", conflict_set(rules, wm))


print("\nEXERCISE 2")
print("------------")

rules_with_not = [
    {
        "id": "R1",
        "conditions": ["A", "B"],
        "conclusion": "C"
    },
    {
        "id": "R2",
        "conditions": ["B", "NOT C"],
        "conclusion": "D"
    },
    {
        "id": "R3",
        "conditions": ["NOT A"],
        "conclusion": "E"
    }
]

wm = {"B"}

print("WM:", wm)
print("Conflict Set:", conflict_set(rules_with_not, wm))

wm.add("A")

print("\nWM:", wm)
print("Conflict Set:", conflict_set(rules_with_not, wm))

wm.add("C")

print("\nWM:", wm)
print("Conflict Set:", conflict_set(rules_with_not, wm))


print("\nEXERCISE 3")
print("------------")

def generate_rules(n):
    rules = []

    for i in range(n):
        rules.append({
            "id": f"R{i}",
            "conditions": ["A", "B"],
            "conclusion": f"C{i}"
        })

    return rules


wm = {"A", "B"}

for size in [100, 500, 1000, 2000, 5000]:

    test_rules = generate_rules(size)

    start = time.perf_counter()

    conflict_set(test_rules, wm)

    end = time.perf_counter()

    print(f"{size} rules: {end - start:.6f} seconds")