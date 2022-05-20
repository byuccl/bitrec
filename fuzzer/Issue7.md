This is related to #6 and is specifically about GFAN0->>BYP_ALT1.

There are two downhill pips from this.

The first one is BYP_ALT1->>BYP_BOUNCE1
and from there many solutions found with a depth 4 or 5 search.

The second one is BYP_ALT1->>BYP_L1
and it ONLY terminates into a SLICEM AX input.
This is not a valid site pin in the current code
and so will not be used.

Thus, restricting the PIP fuzzer to only use SLICEL or TIEOFF sites
(which the code does) means this pip can NEVER be solved because
ALL solutions will include BYP_ALT1->>BYP_BOUNCE on the downhill side.

One solution would be to allow slicem site pins but restrict
it to pins that are common with slicel's.
That is, a slicem and can be used identically to a slicel.
There is no need to use the extended slicem functionality.

I have tested this with my own recursive search and modified version
of is_valid_SP() and it does find multiple disjoint solutions for the
downhill pips. :-)

However, this has also shown that many of the uphill PIP solutions also use
the BYP_ALT1->>BYP_BOUNCE1 pip.
If the pip order is randomized enough times an uphill solution which does not use
that particular PIP will eventually be found. But, it may take many iterations.

I was curious if there was a deterministic way to solve for this.
It seems the requirements are that you need
a. a pair of uphill solutions that are disjoint from each other (have no common pips),
b) a pair of downhill solutions that are disjoint from each other (have no common pips).
c. and, you also need to make sure that these two pairs of solutions are disjoint from one another as well.

It may be computationally intense, but conceptually it should result in a solution for a given PIP
in exactly one pass if such a solution exists. The trade-off is fewer iterations
in Vivado against a possibly more computationally intense python search for a solution.

I have coded up a test program as follows and it does find a solution for this otherwise impossible to solve pip in one iteration:

For a given search depth, find all solutions uphill and put them in a list (usolutions).
Do the same for downhill solutions and put them in a separate list (dsolutions).
Identify ALL pair-wise disjoint solutions from usolutions and put them in a new list.
Do the same from dsolutions.
Now, find some pair from the list from 3 that is disjoint with some pair from 4.
The result is a guaranteed solution for the PIP because you have two uphill solutions, two downhill solutions
and all four are disjoint for one another. The test program does find such a solution for this pip.

if usolutions and dsolutions were sorted by length of solution it would further bias steps 3-5 to find the smallest solution possible, further reducing the number of needed Vivado runs.