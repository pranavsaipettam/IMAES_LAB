"""
AI401 -- Intelligent Multi-Agent and Expert Systems
Experiment 3: Agent Architectures -- The BDI Deliberation Cycle
=================================================================

WHAT THIS FILE IS
------------------
A self-contained implementation of a Belief-Desire-Intention (BDI) agent
operating in a simplified Tileworld, plus the two exercises from the lab
sheet (gamma-vs-dynamism sweep, and a resource-bounded filter). Everything
lives in one file so it is easy to paste into a report and re-run.

WHY A TILEWORLD
----------------
The lab needs an environment that is dynamic *independently* of the agent,
so that "deliberation has a cost" is a real, measurable effect and not just
a design story. Tileworld gives us that for free: holes (desires) appear
and expire on their own clock while the agent is busy thinking or walking.
Effectiveness (holes filled / holes that ever appeared) is the standard
Kinny & Georgeff metric for exactly this reason -- it normalises for how
much opportunity the environment actually offered.

HOW THE CODE MAPS TO THE FOUR BDI FUNCTIONS (Algorithm 1)
-----------------------------------------------------------
    brf(B, p)        -> BDIAgent.brf()        belief revision from percepts
    options(B, I)     -> BDIAgent.options()     desire generation
    filter(B, D, I)   -> BDIAgent.filter()      deliberation / commitment
    plan(B, I)        -> BDIAgent.make_plan()   means-ends reasoning

Algorithm 2 (single-minded reconsideration, parameterised by gamma) is
implemented in BDIAgent.reconsider(). Step 3 of Algorithm 2 -- "charge one
agent time step to deliberation" -- is the crux of the whole experiment:
if we let the agent look at the world for free, cautious (gamma=1) agents
would always win, which would make the gamma-vs-dynamism trade-off
disappear. We literally call world.tick() before the agent gets to look,
so thinking costs exactly what acting costs.
"""

import random
import statistics
from collections import deque
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 1. THE ENVIRONMENT
# ---------------------------------------------------------------------------
class Tileworld:
    """A 15x15 grid on which holes (desires) appear and expire on their own.

    Design choices, and why:
      - spawn_prob is a per-tick Bernoulli trial (matches the lab's "fixed
        probability per world tick" spec) rather than a Poisson process --
        simpler to reason about and to tune for a target dynamism.
      - lifetime is drawn uniformly in [min_life, max_life] so holes expire
        at different, unpredictable times -- this is what makes an
        intention "become impossible" and is what the reconsideration
        machinery in Algorithm 2 exists to detect.
      - world "dynamism" (ticks per agent action) is NOT baked into this
        class: the caller decides how many times to call tick() per agent
        action, because dynamism is a property of the *experiment*, not of
        the world itself.
    """

    def __init__(self, size=15, spawn_prob=0.15, min_life=25, max_life=90, seed=None):
        self.size = size
        self.spawn_prob = spawn_prob
        self.min_life = min_life
        self.max_life = max_life
        self.rng = random.Random(seed)
        self.holes = {}          # pos -> remaining lifetime (ticks)
        self.total_appeared = 0  # denominator for effectiveness

    def tick(self):
        """Advance the world by one tick: age and expire holes, maybe spawn one."""
        expired = []
        for pos in list(self.holes):
            self.holes[pos] -= 1
            if self.holes[pos] <= 0:
                expired.append(pos)
        for pos in expired:
            del self.holes[pos]

        if self.rng.random() < self.spawn_prob:
            pos = (self.rng.randrange(self.size), self.rng.randrange(self.size))
            if pos not in self.holes:
                self.holes[pos] = self.rng.randint(self.min_life, self.max_life)
                self.total_appeared += 1
        return expired

    def fill(self, pos):
        """Score a hole. Returns True iff a hole actually existed there."""
        if pos in self.holes:
            del self.holes[pos]
            return True
        return False


# ---------------------------------------------------------------------------
# 2. THE AGENT
# ---------------------------------------------------------------------------
class BDIAgent:
    """A BDI agent whose commitment strategy is selected explicitly.

    strategy in {"blind", "single_minded", "open_minded"}:
      - blind:         never reconsiders mid-plan; only re-deliberates once
                        the current plan is exhausted (walked to the target
                        cell, whether or not a hole is still there).
                        -> "holds an intention until believed achieved"
      - single_minded:  every gamma actions, re-checks ONLY whether the
                        intention is still achievable; drops it if not, but
                        does not defect to a merely-better option.
      - open_minded:    every gamma actions, re-runs options+filter in
                        full; drops the intention if it is unachievable AND
                        switches to a better one if one exists.
                        -> this is the most expensive strategy per
                        reconsideration, but the most reactive.

    gamma is the reconsideration interval (actions between successive
    deliberations). gamma=1 is the maximally cautious agent; gamma greater
    than the length of any plan makes reconsideration never trigger, which
    is the "bold" agent from the theory section.
    """

    def __init__(self, start_pos, gamma, strategy="single_minded"):
        self.pos = start_pos
        self.gamma = gamma
        self.strategy = strategy

        self.I = None            # current intention: a hole position, or None
        self.plan = deque()      # pi: queue of (x, y) cells left to visit
        self.s = 0               # actions executed since last reconsideration

        self.holes_filled = 0
        self.events = []         # human-readable trace: commit/achieve/drop/switch

    # -- brf(B, p) --------------------------------------------------------
    def brf(self, world):
        """Belief revision. Perception here is perfect and global (every
        currently-live hole is visible) -- a simplification the lab allows,
        since the point of Experiment 3 is commitment, not partial
        observability. Returns the new belief set (a dict pos -> lifetime)."""
        return dict(world.holes)

    # -- options(B, I) ------------------------------------------------------
    def options(self, beliefs):
        """Desire generation: every known hole is a candidate desire.
        Desires are NOT commitments -- this list is allowed to conflict
        (an agent can only fill one hole at a time)."""
        return list(beliefs.keys())

    # -- filter(B, D, I) ----------------------------------------------------
    def filter(self, beliefs, desires, current_intention):
        """Deliberation proper / conflict resolution: pick the desire that
        is cheapest to satisfy. We use Manhattan distance as the cost
        (this IS the "match phase" reused from Experiment 2, since a plan
        schema -- walk in a straight Manhattan path -- is applicable to
        every hole). Ties are broken in favour of the hole with the most
        remaining lifetime, so we don't commit to something about to
        expire when an equally-close alternative will last longer."""
        if not desires:
            return None

        def cost(h):
            dist = abs(h[0] - self.pos[0]) + abs(h[1] - self.pos[1])
            return (dist, -beliefs[h])

        return min(desires, key=cost)

    # -- plan(B, I) -----------------------------------------------------------
    def make_plan(self, target):
        """Means-ends reasoning: the grid has no obstacles, so the shortest
        plan to a hole is simply a Manhattan walk (all x-moves, then all
        y-moves). Returns a queue of cells to step onto in order."""
        moves = deque()
        x, y = self.pos
        tx, ty = target
        while x != tx:
            x += 1 if tx > x else -1
            moves.append((x, y))
        while y != ty:
            y += 1 if ty > y else -1
            moves.append((x, y))
        return moves

    # -- deliberate: steps 3 of Algorithm 1 (also used by open-minded
    #    reconsideration in Algorithm 2 step 5) -----------------------------
    def _deliberate(self, world, tag=""):
        beliefs = self.brf(world)
        desires = self.options(beliefs)
        new_I = self.filter(beliefs, desires, self.I)

        if new_I != self.I:
            if self.I is None:
                self.events.append(f"{tag}COMMIT   -> intention {new_I}")
            else:
                self.events.append(f"{tag}SWITCH   {self.I} -> {new_I}")
        self.I = new_I
        self.plan = self.make_plan(self.I) if self.I is not None else deque()

    # -- Algorithm 2: reconsideration under the chosen commitment strategy --
    def reconsider(self, world):
        self.s += 1

        if self.strategy == "blind":
            # Blind commitment never reconsiders mid-plan; it only gives up
            # once the plan runs out (handled by the main loop noticing an
            # empty plan and re-deliberating "for free" at that point).
            return

        if self.s < self.gamma:
            return  # still inside the commitment window: stay the course

        self.s = 0

        # --- Algorithm 2, step 3: deliberation costs a world tick ---------
        # This is the single most important line in the whole experiment.
        # Without it, gamma=1 dominates every world speed, because looking
        # would be free. Charging a tick here is what lets a faster world
        # start punishing cautious agents less than it punishes bold ones
        # relative to their own plan lengths, and vice versa -- i.e. it is
        # what makes the gamma-vs-dynamism trade-off in Exercise 1 real.
        world.tick()

        beliefs = self.brf(world)

        if self.I not in beliefs:
            # The hole we were chasing has expired: the intention is no
            # longer achievable. Both single-minded and open-minded drop it
            # here (that's the "single-minded" half of open-mindedness).
            self.events.append(f"DROP     {self.I} (no longer achievable)")
            self.I = None
            self.plan = deque()
            return

        if self.strategy == "single_minded":
            # Achievability re-checked (done above); do NOT defect to a
            # merely-better option even if one now exists.
            return

        # strategy == "open_minded": also re-run full deliberation, so the
        # agent can defect to a better intention, not just drop a dead one.
        desires = self.options(beliefs)
        preferred = self.filter(beliefs, desires, self.I)
        if preferred != self.I:
            self.events.append(f"SWITCH   {self.I} -> {preferred} (better option found)")
            self.I = preferred
            self.plan = self.make_plan(self.I)


# ---------------------------------------------------------------------------
# 3. THE MAIN CONTROL LOOP  (Algorithm 1)
# ---------------------------------------------------------------------------
def run_episode(gamma, strategy="single_minded", world_speed=1, steps=600, seed=0):
    """Run one Tileworld episode and return (agent, world, effectiveness).

    world_speed = number of world ticks that occur per agent action; this
    is the lab's "world dynamism" knob. Larger world_speed => the world
    changes faster relative to how much the agent gets to act.
    """
    world = Tileworld(seed=seed)
    start = (world.size // 2, world.size // 2)
    agent = BDIAgent(start, gamma=gamma, strategy=strategy)

    for _ in range(steps):
        # --- step 2: perceive/revise beliefs happens implicitly inside
        #     _deliberate()/reconsider() via brf(); we don't need a
        #     separate call here because nothing in this simplified
        #     Tileworld changes the agent's own position externally.

        # --- step 3: (re)generate intention & plan if we don't have one ---
        if agent.I is None or not agent.plan:
            agent._deliberate(world)

        if not agent.plan:
            # options(B, I) came back empty: nothing to do, let the world
            # advance on its own (Algorithm 1, step 3, "take no action").
            for _ in range(world_speed):
                world.tick()
            continue

        # --- step 4: execute one action of the plan ------------------------
        agent.pos = agent.plan.popleft()
        for _ in range(world_speed):
            world.tick()

        # --- step 5: check whether the intention is achieved ---------------
        if agent.pos == agent.I and agent.pos in world.holes:
            world.fill(agent.pos)
            agent.holes_filled += 1
            agent.events.append(f"ACHIEVE  {agent.I}")
            agent.I = None
            agent.plan = deque()
            agent.s = 0
        elif not agent.plan and agent.strategy == "blind":
            # Blind agent walked its whole plan out but the hole is gone
            # (or was never re-checked) -- give up now, at zero cost, and
            # let step 3 of the next cycle re-deliberate.
            if agent.I is not None:
                agent.events.append(f"DROP     {agent.I} (blind agent reached target, gone)")
            agent.I = None
        else:
            # --- step 6: Algorithm 2 -- decide whether to reconsider -------
            agent.reconsider(world)

    effectiveness = agent.holes_filled / world.total_appeared if world.total_appeared else 0.0
    return agent, world, effectiveness


# ---------------------------------------------------------------------------
# 4. DEMO RUN -- prints an event trace + the headline numbers the lab asks
#    the "Procedure and Result" section to report.
# ---------------------------------------------------------------------------
def demo(gamma=4, strategy="single_minded", world_speed=2, steps=600, seed=42, max_events=25):
    agent, world, eff = run_episode(gamma, strategy, world_speed, steps, seed)

    print(f"=== BDI Tileworld demo | strategy={strategy}  gamma={gamma}  "
          f"world_speed={world_speed}  steps={steps} ===\n")
    print(f"Event trace (first {max_events} of {len(agent.events)} events):")
    for e in agent.events[:max_events]:
        print("  " + e)

    print("\nResults:")
    print(f"  Holes appeared   : {world.total_appeared}")
    print(f"  Holes filled     : {agent.holes_filled}")
    print(f"  Effectiveness    : {eff:.3f}")
    return agent, world, eff


# ---------------------------------------------------------------------------
# 5. EXERCISE 1 -- Boldness against dynamism
# ---------------------------------------------------------------------------
def exercise1_sweep(gammas=(1, 2, 4, 8, "bold"),
                     world_speeds=(1, 2, 4, 8),
                     n_seeds=25,
                     steps=600,
                     strategy="single_minded"):
    """Sweep gamma x world_speed, averaging effectiveness over n_seeds random
    seeds each, as the lab requires. "bold" is realised as a gamma larger
    than any plan can possibly be (grid diagonal is 2*15=30 cells, so any
    gamma > steps guarantees reconsideration never triggers).

    Returns a dict {(gamma_label, world_speed): mean_effectiveness} plus a
    printed table, and (if matplotlib is available) saves a plot.
    """
    results = {}
    for g in gammas:
        gamma_value = steps + 1 if g == "bold" else g
        for ws in world_speeds:
            effs = [
                run_episode(gamma_value, strategy, ws, steps, seed=s)[2]
                for s in range(n_seeds)
            ]
            results[(g, ws)] = statistics.mean(effs)

    # --- tabulate -----------------------------------------------------------
    print(f"\nExercise 1: mean effectiveness over {n_seeds} seeds "
          f"({steps} agent steps each)\n")
    header = "gamma".ljust(8) + "".join(f"speed={ws}".rjust(12) for ws in world_speeds)
    print(header)
    for g in gammas:
        row = str(g).ljust(8) + "".join(
            f"{results[(g, ws)]:.3f}".rjust(12) for ws in world_speeds
        )
        print(row)

    # --- best gamma per speed -------------------------------------------
    print("\nBest gamma at each world speed:")
    for ws in world_speeds:
        best_g = max(gammas, key=lambda g: results[(g, ws)])
        print(f"  speed={ws:<3} -> best gamma = {best_g}  "
              f"(effectiveness={results[(best_g, ws)]:.3f})")

    # WHY the optimum falls as the world speeds up: a bold agent's plan is
    # only optimal at the instant it commits; the longer it walks without
    # re-checking (large gamma), the more likely the target hole has
    # expired or a closer one has appeared before it arrives. Slow worlds
    # rarely invalidate a plan, so the deliberation *cost* (a wasted world
    # tick that could have been movement) dominates -- bold wins. Fast
    # worlds invalidate plans often, so the *benefit* of catching that
    # early dominates -- cautious wins. Both extremes lose for a different
    # reason: gamma=1 spends so many ticks thinking it barely moves even
    # when nothing needs re-checking; "bold" wastes entire plans chasing
    # holes that vanished steps ago -- hence an intermediate gamma wins.

    # --- optional plot --------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.figure(figsize=(7, 5))
        for g in gammas:
            ys = [results[(g, ws)] for ws in world_speeds]
            plt.plot(world_speeds, ys, marker="o", label=f"gamma={g}")
        plt.xlabel("World dynamism (ticks per agent action)")
        plt.ylabel("Mean effectiveness")
        plt.title("Effectiveness vs. dynamism for different commitment strategies")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig("exercise1_gamma_vs_dynamism.png", dpi=150)
        print("\nPlot saved to exercise1_gamma_vs_dynamism.png")
    except ImportError:
        print("\n(matplotlib not available -- skipped plot; table above still holds)")

    return results


# ---------------------------------------------------------------------------
# 6. EXERCISE 2 -- A resource-bounded filter (battery + charger)
# ---------------------------------------------------------------------------
class BatteryAgent(BDIAgent):
    """Extends BDIAgent with a battery and a two-schema plan library.

    WHICH BDI COMPONENT THE FIX BELONGS IN, AND WHY NOT THE PLANNER:
    The battery constraint changes which options are *worth pursuing*, not
    how to walk to a cell once chosen -- the shortest path to a hole is
    still just a Manhattan walk. So the fix belongs in filter() (the
    conflict-resolution / commitment step), which is exactly where
    applicability of a plan schema is supposed to be judged, per the
    theory section's note that "testing whether a plan schema is
    applicable is the match phase of Experiment 2". Putting the battery
    check in plan() would conflate means-ends reasoning (path-finding)
    with deliberation (should we even try), and would force the planner
    to know about goals it has no business evaluating.
    """

    def __init__(self, start_pos, charger_pos, gamma, capacity=40, strategy="single_minded"):
        super().__init__(start_pos, gamma, strategy)
        self.charger_pos = charger_pos
        self.capacity = capacity
        self.battery = capacity
        self.stranded_steps = 0  # agent at 0 battery, away from charger

    @staticmethod
    def _dist(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def filter(self, beliefs, desires, current_intention):
        """fill-hole schema is applicable only if battery covers
        (trip to hole) + (return from hole to charger). recharge is
        always applicable. Commit to the nearest feasible hole; if none
        is feasible, commit to the charger."""
        feasible = [
            h for h in desires
            if self._dist(self.pos, h) + self._dist(h, self.charger_pos) <= self.battery
        ]
        if feasible:
            def cost(h):
                d = self._dist(self.pos, h)
                return (d, -beliefs[h])
            return min(feasible, key=cost)
        return self.charger_pos  # recharge schema: always applicable

    def step_cost(self):
        """Call once per grid cell moved. Battery drains by 1 per move and
        refills at the charger."""
        self.battery -= 1
        if self.pos == self.charger_pos:
            self.battery = self.capacity
        if self.battery <= 0 and self.pos != self.charger_pos:
            self.stranded_steps += 1


def run_battery_episode(gamma, capacity=40, battery_blind=False,
                         world_speed=1, steps=600, seed=0):
    """battery_blind=True reproduces the naive agent that always chases the
    nearest hole regardless of battery, for comparison."""
    world = Tileworld(seed=seed)
    start = (world.size // 2, world.size // 2)
    charger = (0, 0)
    agent = BatteryAgent(start, charger, gamma, capacity=capacity)
    if battery_blind:
        # Battery-blind: filter ignores battery, always chases nearest hole.
        agent.filter = lambda beliefs, desires, cur: BDIAgent.filter(agent, beliefs, desires, cur)

    for _ in range(steps):
        if agent.I is None or not agent.plan:
            agent._deliberate(world)
        if not agent.plan:
            for _ in range(world_speed):
                world.tick()
            continue

        agent.pos = agent.plan.popleft()
        agent.step_cost()
        for _ in range(world_speed):
            world.tick()

        if agent.pos == agent.I and agent.pos in world.holes:
            world.fill(agent.pos)
            agent.holes_filled += 1
            agent.I = None
            agent.plan = deque()
            agent.s = 0
        elif agent.pos == agent.I:  # reached the charger target
            agent.I = None
            agent.plan = deque()
            agent.s = 0
        else:
            agent.reconsider(world)

    return agent, world


def exercise2_compare(n_seeds=25, steps=600, gamma=4, capacity=40):
    smart_filled, smart_stranded = [], []
    blind_filled, blind_stranded = [], []

    for s in range(n_seeds):
        a, w = run_battery_episode(gamma, capacity, battery_blind=False, seed=s, steps=steps)
        smart_filled.append(a.holes_filled)
        smart_stranded.append(a.stranded_steps)

        a2, w2 = run_battery_episode(gamma, capacity, battery_blind=True, seed=s, steps=steps)
        blind_filled.append(a2.holes_filled)
        blind_stranded.append(a2.stranded_steps)

    print(f"\nExercise 2: battery-aware vs battery-blind, {n_seeds} seeds, "
          f"{steps} steps, capacity={capacity}\n")
    print(f"{'':22}{'holes filled':>15}{'stranded steps':>18}")
    print(f"{'battery-aware':22}{statistics.mean(smart_filled):>15.2f}"
          f"{statistics.mean(smart_stranded):>18.2f}")
    print(f"{'battery-blind':22}{statistics.mean(blind_filled):>15.2f}"
          f"{statistics.mean(blind_stranded):>18.2f}")


# ---------------------------------------------------------------------------
# 7. ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # --- Experiment 3 base run: paste this trace + numbers into the report
    demo(gamma=4, strategy="single_minded", world_speed=2, steps=600, seed=42)

    # --- Exercise 1: gamma vs. dynamism sweep -------------------------------
    # NOTE: the lab asks for >=25 seeds x 600 steps x 5 gammas x 4 speeds,
    # which is ~30,000 episode-runs' worth of ticks -- reduce n_seeds below
    # for a quick sanity check, then bump it back to 25 for the real report.
    exercise1_sweep(n_seeds=10, steps=600)

    # --- Exercise 2: resource-bounded filter -------------------------------
    exercise2_compare(n_seeds=10, steps=600)
