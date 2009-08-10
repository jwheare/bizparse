#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
bizparse.py

A scraper for parsing the House of Commons Future Business pages
http://www.publications.parliament.uk/pa/cm/cmfbusi/fbusi.htm

--------

Copyright (c) James Wheare
All rights reserved.
 
Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:
 
    1. Redistributions of source code must retain the above copyright notice, 
       this list of conditions and the following disclaimer.
    
    2. Redistributions in binary form must reproduce the above copyright 
       notice, this list of conditions and the following disclaimer in the
       documentation and/or other materials provided with the distribution.
 
    3. Neither the name of James Wheare nor the names of its contributors may be used
       to endorse or promote products derived from this software without
       specific prior written permission.
 
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import urllib2
import re
import sys
import datetime, time
from BeautifulSoup import BeautifulSoup as BS
from xml.etree import cElementTree as ET
from xml.dom import minidom

WHITESPACE_RE = re.compile(u'\s+')
COMMITTEE_RE = re.compile(u'(?P<amended>As|Not) amended in the Public Bill Committee, to be considered.')

class FutureBusiness:
    """
    House of Commons Future Business
    """
    def __init__ (self, session, part, period):
        self.title = u"House of Commons Future Business"
        self.session = session
        self.part = part
        self.period = period

class Session:
    """
    A session of parliament
    """
    def __init__ (self, start, end):
        self.start = start
        self.end = end

class Period:
    """
    A period of future parliamentary business, with an end date and list of Days
    """
    def __init__ (self, title, subtitle, ending, days = None):
        self.title = title
        self.subtitle = subtitle
        self.ending = ending
        self.days = days

class Day:
    """
    A day of parliamentary business, with a list of BusinessItems
    """
    def __init__ (self, date, business):
        self.date = date
        self.business = business

class BusinessItem:
    """
    An item of parliamentary business with an optional list of bills up for debate
    """
    def __init__ (self, text = None, bills = None):
        self.text = text
        self.bills = bills
    
    def __unicode__ (self):
        return unicode(u'• %s' % self.text)

class PrivateMembersBill:
    """
    A bill proposed by a back bencher (in contrast to a Government proposed bill)
    The bill name, stage, originating house, member in charge are represented
    and whether the bill's reading has been previously adjourned, or amended
    in the Public Bills Committee, along with any accompanying motion
    """
    def __init__ (self, name, stage = None, committee_amended = False, house = False, member = None, adjourned = False, motion = None):
        self.name = name
        self.stage = stage
        self.committee_amended = committee_amended
        self.house = house
        self.member = member
        self.adjourned = adjourned
        self.motion = motion
    
    def __unicode__ (self):
        adjourned = u''
        motion = u''
        committee_amended = u''
        if self.committee_amended:
            committee_amended = u' (Amended in Public Bill Committee)'
        if self.adjourned:
            adjourned = u'\nAdjourned: %s' % self.adjourned
        if self.motion:
            motion = u'\nMotion: %s' % self.motion
        return u"""%s: %s%s
House: %s
Member: %s%s%s""" % (self.name, self.stage, committee_amended, self.house, self.member, adjourned, motion)

class ParseException (Exception):
    pass

class BusinessParser:
    """
    A scraper for parsing the House of Commons Future Business pages
    http://www.publications.parliament.uk/pa/cm/cmfbusi/fbusi.htm
    """
    
    url_root = "http://www.publications.parliament.uk/pa/cm/cmfbusi/"
    file_root= "html/"
    parts = {
        "index": "fbusi.htm",
        "business": "a01.htm",
        "westminster": "b01.htm",
        "remaining": "c01.htm",
        "other": "d01.htm",
        "european": "e01.htm",
        "statements": "f01.htm",
    }
    
    def get_url (self, part):
        if not part:
            return self.url_root
        return "%s%s" % (self.url_root, self.parts[part])
    def get_file_path (self, part):
        if not part:
            return self.file_root
        return "%s%s" % (self.file_root, self.parts[part])
    
    def get_doc (self, name, local = True):
        if local:
            # Read from the file system
            page = open(self.get_file_path(name), 'r')
        else:
            # Read from the web
            url = self.get_url(name)
            page = urllib2.urlopen(url)
        # FIXME: Deal with ampersands/entities
        doc = BS(page, convertEntities=BS.HTML_ENTITIES)
        return doc
    
    def parse_days (self, period, days):
        business_days = []
        for day in days:
            # Add the period year onto the end
            date = u'%s %s' % (day.find('div', 'paraFutureBusinessDate').string.strip(), period.ending.year)
            time_tuple = time.strptime(date, u'%A %d %B %Y')
            biz_date = datetime.date(*time_tuple[0:3])
            # Handle periods that span year boundaries
            if biz_date.month is 12 and period.ending.month is not 12:
                biz_date = datetime.date(period.ending.year - 1, biz_date.month, biz_date.day)
            business = []
            for item in day.findAll('div', 'paraFutureBusinessListItem'):
                # Skip first child (img) and then join the rest of the children (formatting tags for e.g. [Lords] split it up)
                text = ''.join([n.string or n for n in item.contents[1:]]).strip().replace('\n', '')
                if not text:
                    raise ParseException, 'No text for business item: %s' % item
                item_text = re.sub(WHITESPACE_RE, ' ', text)
                bills = self.parse_bills(period, item.findNextSibling('table', 'BusinessItem'))
                item = BusinessItem(text=item_text, bills=bills)
                business.append(item)
            day_data = Day(date=biz_date, business=business)
            business_days.append(day_data)
        return business_days
    
    def parse_session (self, content):
        session = content.find('table').findAll('td')[1].b.string.replace(u'Session ' ,'').strip().replace(u'\xa0', '').strip()
        start, end = session.split('-')
        if len(end) is 2:
            end = '%s%s' % (start[0:2], end)
        return Session(
            start=start,
            end=end
        )
    
    def parse_a_period (self, business):
        heading = business.find('div', 'paraFutureBusinessDivisionHeading').contents[2].strip()
        # Parse the title and end date
        period_title = heading
        period_matches = re.match('.*period ending on (?P<period>.*)', heading)
        if not period_matches:
            raise ParseException, "No matching period date: %s" % heading
        ending = period_matches.group('period')
        time_tuple = time.strptime(ending, '%A %d %B %Y')
        period_ending = datetime.date(*time_tuple[0:3])
        # Subtitle
        subheading = business.find('div', 'paraFutureBusinessDivisionNote')
        period_subtitle = re.sub(WHITESPACE_RE, ' ', subheading.string.replace('\n', '').replace('&nbsp;', ' ').strip())
        period = Period(period_title, period_subtitle, period_ending)
        days = business.findAll('div', 'FutureBusinessDay')
        period.days = self.parse_days(period, days)
        return period
    
    def parse_bills (self, period, bill_doc):
        if not bill_doc:
            return None
        bills = []
        for row in bill_doc.tbody.findAll('tr'):
            bill_row = row.find('tr')
            # This will give us the bill detail rows
            # We get the member and adjournment rows with findNextSiblings
            if bill_row:
                headings = bill_row.findAll('div', 'paraFBPrivateMembersBillItemHeading')
                if headings:
                    bill_house = 'commons'
                    bill_member = None
                    bill_motion = None
                    bill_adjourned = False
                    bill_committee_amended = False
                    
                    # First heading is just the number, so take the second to find name and stage
                    bill_details = headings[1].contents
                    if len(bill_details) is 1:
                        bill_name, bill_stage = bill_details[0].strip().split(u': ')
                    elif len(bill_details) is 3:
                        # Lords qualifier <span> splits the content up
                        bill_name = bill_details[0].rstrip(u'[').strip()
                        bill_stage = bill_details[2].replace(u': ', u'').lstrip(u']').strip()
                        bill_house = u'lords'
                    else:
                        raise ParseException, 'Unexpected heading splitting: %s' % bill_details
                    # Check bill stage for Public Committee Consideration
                    # TODO: Support for other stages
                    committee_parts = re.match(COMMITTEE_RE, bill_stage)
                    if committee_parts:
                        bill_committee_amended = committee_parts.group('amended') == u'As'
                        bill_stage = u'Report stage'
                    # Check for adjournment
                    adjourned_parts = re.match(u'Adjourned debate on (?P<stage>.+) \[(?P<date>.+)\]', bill_stage)
                    if adjourned_parts:
                        bill_stage = adjourned_parts.group('stage')
                        # Add the period year onto the end
                        date = '%s %s' % (adjourned_parts.group('date'), period.ending.year)
                        time_tuple = time.strptime(date, '%d %B %Y')
                        bill_adjourned = datetime.date(*time_tuple[0:3])
                        # Handle periods that span year boundaries
                        if bill_adjourned.month is 12 and period.ending.month is not 1:
                            bill_adjourned = datetime.date(period.ending.year - 1, bill_adjourned.month, bill_adjourned.day)
                    # Parse member in charge and motion from the next rows
                    for next_row in row.findNextSiblings('tr', limit=2):
                        member_row = next_row.find('div', 'paraMemberinCharge')
                        motion_row = next_row.find('div', 'paraMotionText')
                        if member_row:
                            bill_member = member_row.string.replace(u'Member in charge:\xa0', u'').strip()
                        if motion_row:
                            bill_motion = motion_row.string.replace(u'\xa0', u'').strip()
                    # Trim superfluities
                    bill_name = bill_name.rstrip(u' BILL')
                    bill_stage = bill_stage.rstrip(u'.')
                    
                    bill = PrivateMembersBill(
                        name=bill_name,
                        stage=bill_stage,
                        committee_amended=bill_committee_amended,
                        house=bill_house,
                        member=bill_member,
                        adjourned=bill_adjourned,
                        motion=bill_motion
                    )
                    bills.append(bill)
        return bills
    
    def parse_part (self, content):
        return content.find('span', 'charFutureBusinessDivisionLetter').string.strip()
    
    def parse_a (self):
        part = 'business'
        self.url = self.get_url(part)
        self.fetched = datetime.date.today()
        doc = self.get_doc(part)
        content = doc.find('div', id='maincontent')
        preamble = content.find('p').find('table')
        business = preamble.findNextSibling('table')
        session = self.parse_session(content)
        part = self.parse_part(content)
        period = self.parse_a_period(business)
        future_biz = FutureBusiness(
            session=session,
            part=part,
            period=period
        )
        return future_biz

if __name__ == '__main__':
    parser = BusinessParser()
    future_biz = parser.parse_a()
    # <futurebusiness @url @fetched @session-start @session-end @part>
    root_node = ET.Element('futurebusiness')
    print u'URL: %s' % parser.url
    root_node.set('url', parser.url)
    print u'Date fetched: %s' % parser.fetched
    root_node.set('fetched', parser.fetched.strftime('%Y-%m-%d'))
    print u'========'
    print u'Session: %s-%s' % (future_biz.session.start, future_biz.session.end)
    root_node.set('session-start', future_biz.session.start)
    root_node.set('session-end', future_biz.session.end)
    print u'Future Business Part %s' % future_biz.part
    root_node.set('part', future_biz.part)
    print u'Period ending: %s' % future_biz.period.ending
    # - <title>
    title_node = ET.SubElement(root_node, 'title')
    title_node.text = future_biz.period.title
    # - <title>
    subtitle_node = ET.SubElement(root_node, 'subtitle')
    subtitle_node.text = future_biz.period.subtitle
    # - <period @ending>
    period_node = ET.SubElement(root_node, 'period')
    period_node.set('ending', future_biz.period.ending.strftime('%Y-%m-%d'))
    for day in future_biz.period.days:
        print u'========'
        # -- <day @date>
        day_node = ET.SubElement(period_node, 'day')
        print day.date
        day_node.set('date', day.date.strftime('%Y-%m-%d'))
        for item in day.business:
            # --- <item [@bills]>
            item_node = ET.SubElement(day_node, 'item')
            print item.__unicode__()
            # ---- <text>
            item_text_node = ET.SubElement(item_node, 'text')
            item_text_node.text = item.text
            if item.bills:
                item_node.set('bills', str(len(item.bills)))
                # ---- <bills>
                bills_node = ET.SubElement(item_node, 'bills')
                for bill in item.bills:
                    print u'----'
                    print bill.__unicode__()
                    # ----- <bill @house [@adjourned]>
                    bill_node = ET.SubElement(bills_node, 'bill')
                    bill_node.set('house', bill.house)
                    if bill.adjourned:
                        bill_node.set('adjourned', bill.adjourned.strftime('%Y-%m-%d'))
                    # ------ <name>
                    bill_name_node = ET.SubElement(bill_node, 'name')
                    bill_name_node.text = bill.name
                    # ------ <member>
                    bill_member_node = ET.SubElement(bill_node, 'member')
                    bill_member_node.text = bill.member
                    # ------ <stage [@amended]>
                    bill_stage_node = ET.SubElement(bill_node, 'stage')
                    bill_stage_node.text = bill.stage
                    if  bill.committee_amended:
                        bill_stage_node.set('amended', 'committee')
                    if bill.motion:
                        # [------ <motion>]
                        bill_motion_node = ET.SubElement(bill_node, 'motion')
                        bill_motion_node.text = bill.motion
                print u'----'
    outfile = open('bizparse.xml', 'w')
    xml_doc = ET.ElementTree(root_node)
    xml_doc.write(outfile)
    outfile.close()