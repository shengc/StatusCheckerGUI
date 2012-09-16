'''
   Copyright [2012] [Mianwo]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
'''

import cookielib
import urllib2
import urllib
from HTMLParser import HTMLParser
import re
import json
from time import strptime
import os

import pylab

class MyHTMLParser(HTMLParser):
    """
    For the sake of efficiency, this is not thread safe! 
    """
    keyPattern = re.compile("^Your Current Case Status for Form (.*)$")
    timePattern = re.compile("^On(.*?) we.*$")
    
    def __init__(self):
        self._caseTypeFound=False
        self._caseStatusFound=False
        self._caseTimeFound=False
        self._stat = {}.fromkeys([Checker.type_field, Checker.status_field, Checker.time_field])
        HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.has_key('id') and attrs['id'] == 'caseStatus':
            self._caseTypeFound=True
        elif tag == 'img' and attrs.has_key('src') and 'bucket-on' in attrs['src']:
            self._caseStatusFound = True
        elif attrs.has_key('class') and attrs['class'] == 'caseStatus':
            self._caseTimeFound=True
            
    def handle_endtag(self, tag):
        pass
    def handle_data(self, data):
        if self._caseTypeFound and data.strip():
            mat = MyHTMLParser.keyPattern.match(data.strip())
            if mat is not None:
                self._stat[Checker.type_field] = mat.groups()[0].split(',')[0].strip()
            self._caseTypeFound = False
        elif self._caseStatusFound and data.strip():
            self._stat[Checker.status_field] = data.strip()
            self._caseStatusFound = False
        elif self._caseTimeFound:
            mat = MyHTMLParser.timePattern.match(data.strip())
            if mat is not None:
                self._stat[Checker.time_field] = mat.groups()[0].rsplit(',', 1)[0].strip()
            self._caseTimeFound = False
    
    def __reset(self):
        self._caseTypeFound=False
        self._caseStatusFound=False
        self._caseTimeFound=False
        
    def get(self):
        self.__reset()
        return self._stat.copy()
 
    def feed(self, data):
        self._stat = {}.fromkeys([Checker.type_field, Checker.status_field, Checker.time_field])
        HTMLParser.feed(self, data)

class Checker(object):
    
    base_url = "https://egov.uscis.gov/cris/Dashboard/CaseStatus.do"
    id_pattern = re.compile("^([a-zA-Z]*)([0-9]*)$")
    
    type_field = 'type'
    status_field = 'status'
    time_field = 'time'
    
    def __init__(self):
        self.parser = MyHTMLParser()
    
    @staticmethod
    def response(status_id, log=None):
        assert type(status_id) is str or type(status_id) is unicode, "status_id needs to be a string"

        opener = None
        try:
            cj = cookielib.CookieJar()
            opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
            urllib2.install_opener(opener)
        
            values = dict(appReceiptNum=status_id)
            data = urllib.urlencode(values)
        
            req = urllib2.Request(Checker.base_url, data)
            res = opener.open(req) 
            return res.read()
        except Exception as e:
            if log is not None: log.error("error in processing status_id: %s" % str(e))
            return ""
        finally:
            if opener is not None: opener.close()

    def validateCase(self, status_id):
        self.parser.feed(Checker.response(status_id))
        return reduce(lambda x, y: x and y, [s is not None for s in self.parser.get().values()])

    def taskManager(self, petition_id, query_range, types, log, progress_bar=None, save2file=False):
        assert type(query_range) is int and len(types) > 0
        
        def join(stats, stat):
            if not stats.has_key(stat[Checker.type_field]): stats[stat[Checker.type_field]] = {}
            if not stats[stat[Checker.type_field]].has_key(stat[Checker.status_field]): stats[stat[Checker.type_field]][stat[Checker.status_field]] = {}
            if not stats[stat[Checker.type_field]][stat[Checker.status_field]].has_key(stat[Checker.time_field]): stats[stat[Checker.type_field]][stat[Checker.status_field]][stat[Checker.time_field]] = 0
            stats[stat[Checker.type_field]][stat[Checker.status_field]][stat[Checker.time_field]] += 1
            return stats
        
        mats = Checker.id_pattern.match(petition_id)
        string, number = mats.groups()
        number = int(number)
        count1 = 0
        consec_fail = 0
        incrementor = 0
        
        stats = []
        log.info("Initialization Done! Start lower range search...")
        while count1 < query_range:
            status_id = "%s%d" % (string, (number - incrementor))
            self.parser.feed(Checker.response(status_id, log))
            stat = self.parser.get()
            if stat[self.type_field] in types:
                if reduce(lambda x, y: x and y, [s is not None for s in stat.values()]):
                    log.info("processing %s... Accepted type %s" % (status_id, stat[self.type_field]))
                    stats.append(stat)        
                    count1 += 1
                    if progress_bar is not None: progress_bar.Update(count1)
                    consec_fail = 0
                else:
                    log.info("processing %s... Rejected" % status_id) 
                    consec_fail += 1
            else: log.info("processing %s... Rejected type %s" % (status_id, stat[self.type_field])) 
            
            if consec_fail > 3: break
            incrementor += 1;

        log.info("Lower range search done. Start upper range search...")
            
        remains = query_range - count1
        count2 = 0
        consec_fail = 0
        incrementor = 0
        while count2 < query_range + remains:
            status_id = "%s%d" % (string, (number + incrementor)) 
            self.parser.feed(Checker.response(status_id))
            stat = self.parser.get()
            if stat[self.type_field] in types:                
                if reduce(lambda x, y: x and y, [s is not None for s in stat.values()]):
                    log.info("processing %s... Accepted %s" % (status_id, stat[self.type_field]))
                    stats.append(stat)
                    count2 += 1
                    if progress_bar is not None: progress_bar.Update(count1 + count2)
                    consec_fail = 0
                else: 
                    log.info("processing %s... Rejected" % status_id)
                    consec_fail += 1
            else: log.info("processing %s... Rejected type %s" % (status_id, stat[self.type_field]))
            
            if consec_fail > 3: break
            incrementor += 1

        log.info("Search done. Found %d cases fitting the desired types" % (count1 + count2))
        print "Generating reports...."
        print "=" * 20 + "\n\n\n"
        
        stats = reduce(lambda x, y: join(x, y), stats, {})
        print stats
        
        report = json.dumps(stats, sort_keys=True, indent=4)
        print report
        if save2file:
            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'report.txt'), 'w') as fout:
                fout.write(report)
        
        return stats

class Plotter(object):

    bins = range(1, 12 + 1)
    
    class ColorGenerator(object):
        colors = ['crimson', 'burlywood', 'chartreuse', 'magenta', 'cyan']
        
        def __init__(self):
            self.c = 0
        
        def get(self):
            color = self.colors[self.c]
            self.c = 0 if self.c == len(self.colors) - 1 else (self.c + 1)
            return color
    
    def __init__(self):    
        self.color_generator = Plotter.ColorGenerator()
    
    def plot(self, stats, types):
        for p_type in stats.iterkeys():
            d_data = {}
            for p_stat in stats[p_type].iterkeys():
                for p_time in stats[p_type][p_stat].iterkeys():
                    t = strptime(p_time, "%B %d, %Y")
                    y = t[0]
                    m = t[1]
                    
                    k = '%s:%s' % (y, p_stat)
                    if not d_data.has_key(k): d_data[k] = ([], self.color_generator.get())
                    d_data[k][0].extend([m] * stats[p_type][p_stat][p_time]) 
            
            sort_keys = sorted(d_data.keys())
                
            pylab.figure()
            pylab.xlabel('month')
            pylab.ylabel('numCases')
            pylab.title(p_type)
            pylab.hist([d_data[x][0] for x in sort_keys], Plotter.bins, histtype='barstacked', color=[d_data[x][-1] for x in sort_keys], label=sort_keys)
            pylab.legend()  
        pylab.show() 

if __name__ == '__main__':
    import logging as log
    log.basicConfig(level=log.INFO)
    
    checker = Checker()
    stats = checker.taskManager('SRC1280014743', 20, ['I140', 'I485'], log)
    print stats
    plotter = Plotter()
    plotter.plot(stats, ['I140'])
    
