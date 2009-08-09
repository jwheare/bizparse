bizparse.py

A scraper for parsing the House of Commons Future Business pages
http://www.publications.parliament.uk/pa/cm/cmfbusi/fbusi.htm

====

The biggest challenge was understanding the data so that I could come up with a sensible structure for the output. Luckily there's good info on Wikipedia and the Parliament website explaining exactly what this "business" is.

I wanted to provide useful information about the Private Members Bills, particularly about how far through the process they were. This information is ripe for cross referencing with a more in depth archive of Bills, beyond the Public Bill Committee pages on TWFY.

One limitation of this scraper is that it has mainly been written for one page (Part A), and remains to be tested against updates to Future Business. An archive of these updates would have been useful to test its robustness. I've made some efforts to catch parsing errors should this script need to be run against an incompatible document so that areas for improvement can be more easily identified. There are doubtless many other forms these pages could take that are not yet handled by the main parser.

Part A shares some elements with the other parts that the scraper could be extended to cope with, though I didn't focus on them for this task.

I had a look through the other scripts in pyscraper, though it was hard to tell which were still in use and would be relevant for this task. In the end I made my own decisions based on looking through the existing parlparse output formats and my own common sense. The format I chose can easily be modified as the data is all available via a Python API included with the script.