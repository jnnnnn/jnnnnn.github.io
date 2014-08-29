# Author: Jonathan Newnham
# License: Public Domain

# graph :: { node : [next nodes] }
def cycles(graph, cycle_length, simple=True):
    """Find all cycles of the given number of nodes.
       Each cycle is only found once (i.e. no rotation duplicates).
       Simple: nodes cannot be present more than once in a cycle."""

    # I wonder if this can be optimized more by building up chains from both ends 
    # (i.e. working backwards from the destination node as well as working forward from the source...)
    fully_explored = set()
    if cycle_length < 1:
        return

    def rec(stack):
        cur_node = stack[-1]
        for next_node in graph[cur_node]:
            if next_node in fully_explored:
                continue
            if next_node in stack:
                if next_node == stack[0] and len(stack) == cycle_length:
                    yield stack
                elif simple:
                    continue
            if len(stack) == cycle_length:
                continue
            elif len(stack) == cycle_length - 1 and stack[0] in graph[next_node]:
                # this elif is an optimization to short-circuit the innermost loop (last recursion)
                yield stack + [next_node]
                continue
            for result in rec(stack + [next_node]):
                yield result
        return

    for scc_nodes in strongly_connected_components(graph):
        if len(scc_nodes) < cycle_length:
            continue
        scc_graph = filter_graph(graph, scc_nodes)
        for node in sorted(scc_graph):
            for result in rec([node]):
                yield result
            fully_explored.add(node)


def filter_graph(graph, node_whitelist):
    node_whitelist = set(node_whitelist)
    return {n:[n2 for n2 in graph[n] if n2 in node_whitelist]
            for n in graph if n in node_whitelist}            

def strongly_connected_components(graph):
    """
    Tarjan's Algorithm (named for its discoverer, Robert Tarjan) is a graph theory algorithm
    for finding the strongly connected components of a graph.
    
    Based on: http://en.wikipedia.org/wiki/Tarjan%27s_strongly_connected_components_algorithm

    This is some tricky shit right here.
    """

    index_counter = [0]
    stack = []
    lowlinks = {}
    index = {}
    result = []
    
    def strongconnect(node):
        # set the depth index for this node to the smallest unused index
        index[node] = index_counter[0]
        lowlinks[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
    
        # Consider successors of `node`
        try:
            successors = graph[node]
        except:
            successors = []
        for successor in successors:
            if successor not in lowlinks:
                # Successor has not yet been visited; recurse on it
                strongconnect(successor)
                lowlinks[node] = min(lowlinks[node],lowlinks[successor])
            elif successor in stack:
                # the successor is in the stack and hence in the current strongly connected component (SCC)
                lowlinks[node] = min(lowlinks[node],index[successor])
        
        # If `node` is a root node, pop the stack and generate an SCC
        if lowlinks[node] == index[node]:
            connected_component = []
            
            while True:
                successor = stack.pop()
                connected_component.append(successor)
                if successor == node: break
            component = tuple(connected_component)
            # storing the result
            result.append(component)
    
    for node in graph:
        if node not in lowlinks:
            strongconnect(node)
    
    return result

import unittest
class TestCycle(unittest.TestCase):
    def setUp(self):
        self.test_graph = {
            1:[2],
            2:[3,5],
            3:[1,4],
            4:[],
            5:[3,6],
            6:[5,6]
            }
        self.test_graph_small = {1:[2], 2:[1,3], 3:[]}
    def test_simple_cycle(self):
        self.assertEqual([], sorted(cycles(self.test_graph, 0)))
        self.assertEqual([], sorted(cycles(self.test_graph, 1)))
        self.assertEqual([[5,6]], sorted(cycles(self.test_graph, 2)))
        self.assertEqual([[1,2,3]], sorted(cycles(self.test_graph, 3)))
        self.assertEqual([[1,2,5,3]], sorted(cycles(self.test_graph, 4)))
    def test_repeat_cycle(self):
        self.assertEqual([], sorted(cycles(self.test_graph, 0, False)))
        self.assertEqual([], sorted(cycles(self.test_graph, 1, False)))
        self.assertEqual([[5,6],[6,6]], sorted(cycles(self.test_graph, 2, False)))
        self.assertEqual([[1,2,3], [5, 6, 6], [6, 6, 6]], sorted(cycles(self.test_graph, 3, False)))        
        self.assertEqual([[1,2,5,3],[5,6,5,6], [5, 6, 6, 6], [6, 6, 6, 6]], sorted(cycles(self.test_graph, 4, False)))

if __name__ == '__main__':
    unittest.main()
