knowledge = [
    ("animal", "has", "skin"),
    ("fish", "is-a", "animal"),
    ("shark", "is-a", "fish"),
    ("bird", "can", "fly"),
    ("penguin", "is-a", "bird"),
    ("penguin", "cannot", "fly")
]


def get_parent(node):
    for subject, relation, obj in knowledge:
        if subject == node and relation == "is-a":
            return obj
    return None


def inheritance_chain(node):
    chain = [node]

    while True:
        parent = get_parent(node)

        if parent is None:
            break

        chain.append(parent)
        node = parent

    return chain


def query(node, relation):
    chain = inheritance_chain(node)

    for current in chain:

        # Check exception before inherited property
        for subject, rel, obj in knowledge:
            if subject == current and rel == "cannot":
                if relation == "can":
                    return f"cannot {obj}"

        for subject, rel, obj in knowledge:
            if subject == current and rel == relation:
                return obj

    return "unknown"


def show_knowledge():
    print("\nKnowledge Base:")
    for triple in knowledge:
        print(triple)


print("Semantic Network with Inheritance")

show_knowledge()

print("\nInheritance Chains:")
print("shark:", " -> ".join(inheritance_chain("shark")))
print("penguin:", " -> ".join(inheritance_chain("penguin")))

print("\nQueries:")
print("shark has:", query("shark", "has"))
print("penguin can:", query("penguin", "can"))
print("bird can:", query("bird", "can"))
print("shark can:", query("shark", "can"))


# Exercise 1: Ostrich

knowledge.extend([
    ("ostrich", "is-a", "bird"),
    ("ostrich", "cannot", "fly"),
    ("ostrich", "can", "run-fast")
])

print("\nAfter adding ostrich:")
print("ostrich chain:", " -> ".join(inheritance_chain("ostrich")))
print("ostrich can:", query("ostrich", "can"))
print("ostrich has:", query("ostrich", "has"))


# Exercise 2: Frames

frames = {
    "animal": {
        "has": "skin"
    },
    "fish": {
        "ako": "animal"
    },
    "shark": {
        "ako": "fish"
    },
    "bird": {
        "can": "fly"
    },
    "penguin": {
        "ako": "bird",
        "cannot": "fly"
    },
    "ostrich": {
        "ako": "bird",
        "cannot": "fly",
        "can": "run-fast"
    }
}


def get_frame_parent(frame):
    return frames.get(frame, {}).get("ako")


def frame_chain(frame):
    chain = [frame]

    while True:
        parent = get_frame_parent(frame)

        if parent is None:
            break

        chain.append(parent)
        frame = parent

    return chain


def frame_query(frame, slot):
    for current in frame_chain(frame):
        data = frames[current]

        if "cannot" in data and slot == "can":
            return f"cannot {data['cannot']}"

        if slot in data:
            return data[slot]

    return "unknown"


print("\nFrames:")
for name, data in frames.items():
    print(name, ":", data)

print("\nFrame Queries:")
print("penguin can:", frame_query("penguin", "can"))
print("penguin has:", frame_query("penguin", "has"))
print("ostrich can:", frame_query("ostrich", "can"))


# Exercise 3: Multiple inheritance

multi_knowledge = [
    ("animal", "has", "skin"),
    ("bird", "is-a", "animal"),
    ("bird", "can", "fly"),
    ("swimmer", "is-a", "animal"),
    ("swimmer", "can", "swim"),
    ("duck", "is-a", "bird"),
    ("duck", "is-a", "swimmer")
]


def get_parents(node):
    parents = []

    for subject, relation, obj in multi_knowledge:
        if subject == node and relation == "is-a":
            parents.append(obj)

    return parents


def multi_query(node, relation):
    visited = set()

    def search(current):
        if current in visited:
            return "unknown"

        visited.add(current)

        for subject, rel, obj in multi_knowledge:
            if subject == current and rel == "cannot":
                if relation == "can":
                    return f"cannot {obj}"

        for subject, rel, obj in multi_knowledge:
            if subject == current and rel == relation:
                return obj

        for parent in get_parents(current):
            result = search(parent)

            if result != "unknown":
                return result

        return "unknown"

    return search(node)


print("\nMultiple Inheritance:")
print("duck parents:", get_parents("duck"))
print("duck can:", multi_query("duck", "can"))
print("duck swim:", multi_query("duck", "can"))