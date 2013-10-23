#!/usr/bin/env python

"""
organize-photos.py - Organize an unstructured folder tree of photos by date

Note: This is a minor rewrite of @cliss's extension [1,2] of @drdrang's 
photo management scripts [3], and includes a tweak from @jamiepinkham [4,5].

[1] https://gist.github.com/cliss/6854904
[2] http://tumblr.caseyliss.com/day/2013/10/06
[3] http://www.leancrew.com/all-this/2013/10/photo-management-via-the-finder/
[4] https://gist.github.com/jamiepinkham/6984369
[5] https://twitter.com/drdrang/status/389952079763996672
"""

import sys
import os, os.path
import subprocess
from datetime import datetime

## Edit these paths (relative to home) to set input and output locations
sourcePath = 'Desktop/Photos to Organize'
destPath = 'Pictures/Photos'
## No more editing (unless you're fixing/improving the script)

def get_date_time_of_photo(f):
    try:
        cDate = subprocess.check_output(['sips', '-g', 'creation', f])
        cDate = cDate.split('\n')[1].lstrip().split(': ')[1]
        return datetime.strptime(cDate, "%Y:%m:%d %H:%M:%S")
    except:
        return datetime.fromtimestamp(os.path.getmtime(f))

def get_source_photo_filenames(d):
    p = []
    is_photo = lambda f: os.path.splitext(f)[1].lower() in ('.jpg', '.jpeg', '.jpe')
    for dirpath, dirnames, filenames in os.walk(d):        
        path = os.path.join(d, dirpath)
        p.extend(map(lambda f: os.path.join(path, f), filter(is_photo, filenames)))
    return p

home = os.environ['HOME']
sourceDir = os.path.join(home, sourcePath)
destDir = os.path.join(home, destPath)
errorDir = os.path.join(destDir, 'Unsorted')
print 'Moving from %s to %s.' % (sourceDir, destDir)

photos = get_source_photo_filenames(sourceDir)
print 'Found %d photos to process.' % len(photos)

if not os.path.exists(destDir):
    os.makedirs(destDir)
if not os.path.exists(errorDir):
    os.makedirs(errorDir)

lastMonth = 0
lastYear = 0
fmt = "%Y-%m-%d %H-%M-%S"
problems = []

# Open a log file to record copy operations and errors
logfd = file(os.path.join(destDir, 'organize-photos.log'), 'w')

for original in photos:
    suffix = 'a'
    
    try:
        pDate = get_date_time_of_photo(original)
        yr = pDate.year
        mo = pDate.month

        if (mo, yr) != (lastMonth, lastYear):
            sys.stdout.write('\nProcessing %04d-%02d...' % (yr, mo))
            lastMonth = mo
            lastYear = yr
        else:
            sys.stdout.write('.')

        newname = pDate.strftime(fmt)
        thisDestDir = os.path.join(destDir, '%04d' % yr, '%02d' % mo)
        if not os.path.exists(thisDestDir):
            os.makedirs(thisDestDir)

        duplicate = os.path.join(thisDestDir, '%s.jpg' % newname)
        while os.path.exists(duplicate):
            duplicate = os.path.join(thisDestDir, '%s%s.jpg' % (newname, suffix))
            suffix = chr(ord(suffix) + 1)
            
        if subprocess.call(['cp', '-p', original, duplicate]) != 0:
            raise Exception
        
        print >>logfd, 'Copied: %s -> %s' % (original, duplicate)
        
    except Exception:
        unsorted_photo = os.path.join(errorDir, os.path.basename(original))
        subprocess.call(['cp', '-p', original, unsorted_photo])
        problems.append(original[len(home):])
        print >>logfd, 'Error: unable to copy %s' % original
        
    except:
        sys.exit("Execution stopped.")

if len(problems) > 0:
    print "\nProblem files:"
    print "\n\t".join(problems)
    print "These can be found in: %s" % errorDir
elif len(photos):
    sys.stdout.write('\n')
    
logfd.close()
sys.exit(0)