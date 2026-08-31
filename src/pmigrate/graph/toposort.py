"""Phase 1 step 1.4 (docs/phase-1-graph.md) — order modules leaf-first for migration.

Deliberately backend-independent: this is pure graph theory over an edge list, with no
Neo4j/Cypher involved. docs/phase-1-graph.md is explicit that this is a considered choice,
not a shortcut: "Tarjan in Python over the edges is fine and clearer than fighting Neo4j
GDS." Any CodeGraph backend (Neo4j, in-memory, whatever comes next) can call this after
fetching its edge list, so the algorithm is tested exactly once, here.

Python programs routinely have circular imports, so a plain topological sort isn't
well-defined — modules in a cycle must migrate together. This module finds strongly
connected components (Tarjan) and topologically sorts the condensation (the DAG you get
by collapsing each SCC to a single node), so the result is a list of leaf-first BATCHES,
where a batch is either one module or a whole import cycle.
"""

from __future__ import annotations

from collections import defaultdict


def strongly_connected_components(nodes: set[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Tarjan's algorithm, iterative (recursion depth would otherwise be bounded by the
    deepest import chain, which is exactly the kind of thing a large repo hits)."""
    adjacency: dict[str, list[str]] = defaultdict(list)
    for src, dst in edges:
        if src in nodes and dst in nodes:
            adjacency[src].append(dst)

    index_counter = [0]
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    stack: list[str] = []
    result: list[list[str]] = []

    for start in nodes:
        if start in index:
            continue
        # (node, iterator-index-into-adjacency, parent) work stack for the iterative DFS
        work: list[tuple[str, int]] = [(start, 0)]
        index[start] = lowlink[start] = index_counter[0]
        index_counter[0] += 1
        stack.append(start)
        on_stack[start] = True

        while work:
            node, i = work[-1]
            neighbours = adjacency[node]
            if i < len(neighbours):
                work[-1] = (node, i + 1)
                nxt = neighbours[i]
                if nxt not in index:
                    index[nxt] = lowlink[nxt] = index_counter[0]
                    index_counter[0] += 1
                    stack.append(nxt)
                    on_stack[nxt] = True
                    work.append((nxt, 0))
                elif on_stack.get(nxt):
                    lowlink[node] = min(lowlink[node], index[nxt])
            else:
                work.pop()
                if work:
                    parent = work[-1][0]
                    lowlink[parent] = min(lowlink[parent], lowlink[node])
                if lowlink[node] == index[node]:
                    component = []
                    while True:
                        member = stack.pop()
                        on_stack[member] = False
                        component.append(member)
                        if member == node:
                            break
                    result.append(component)

    return result


def topo_batches(nodes: set[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Leaf-first batches: dependencies before dependents. `edges` are (importer,
    imported) pairs; a batch earlier in the result has nothing in it that depends on a
    later batch. Each inner list is a single module, or a whole SCC if modules import each
    other in a cycle.
    """
    components = strongly_connected_components(nodes, edges)
    component_of: dict[str, int] = {}
    for i, comp in enumerate(components):
        for node in comp:
            component_of[node] = i

    # condensation: edge between component i and component j if any member of i imports
    # any member of j
    comp_edges: set[tuple[int, int]] = set()
    comp_adjacency: dict[int, set[int]] = defaultdict(set)
    for src, dst in edges:
        if src not in component_of or dst not in component_of:
            continue
        ci, cj = component_of[src], component_of[dst]
        if ci == cj:
            continue
        if (ci, cj) not in comp_edges:
            comp_edges.add((ci, cj))
            comp_adjacency[ci].add(cj)

    # Kahn's algorithm on the condensation, but we want dependencies (imported modules)
    # BEFORE dependents (importers), i.e. leaves first — imported modules have no
    # outgoing edges to worry about first, so start from components nothing depends ON
    # being imported LAST... concretely: process components with in-degree 0 in the
    # REVERSED graph (nothing imports them from within the reversed set) — simplest to
    # implement as: start from components that import nothing unprocessed (out-degree 0
    # among remaining), since those are the leaves.
    remaining_out_degree = {i: len(comp_adjacency[i]) for i in range(len(components))}
    ready = [i for i, deg in remaining_out_degree.items() if deg == 0]
    reverse_adjacency: dict[int, set[int]] = defaultdict(set)
    for ci, cj in comp_edges:
        reverse_adjacency[cj].add(ci)

    ordered: list[int] = []
    seen = set(ready)
    frontier = ready
    while frontier:
        ordered.extend(frontier)
        next_frontier = []
        for leaf in frontier:
            for importer in reverse_adjacency[leaf]:
                remaining_out_degree[importer] -= 1
                if remaining_out_degree[importer] == 0 and importer not in seen:
                    seen.add(importer)
                    next_frontier.append(importer)
        frontier = next_frontier

    # anything left didn't reach out-degree 0 through this walk — shouldn't happen on a
    # DAG (the condensation is always a DAG by construction) but guard against a bug
    # rather than silently dropping modules.
    for i in range(len(components)):
        if i not in seen:
            ordered.append(i)

    return [components[i] for i in ordered]
