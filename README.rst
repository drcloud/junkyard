-------
Testing
-------

Run ``tox`` or ``make test``.


-----------------------------------
Why is Dr. Cloud written in Python?
-----------------------------------

Python is not the fastest or least failure prone language. However, it is
approachable and easy to debug (one can always add print statements in the
necessary places, if it comes down to that). The performance needs of Dr.
Cloud are actually fairly modest -- imagine a website that only had a few
thousand active users at any one time. The real challenge with an
infrastructure tool like Dr. Cloud is to make something understandable,
auditable and extendable.

