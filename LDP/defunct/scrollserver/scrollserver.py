#!/usr/bin/python

import os				# Import required modules
import sys
import stat
import string
import commands
import StringIO
import locale
import BaseHTTPServer
import shutil

from urlparse import URI		# Import ScrollServer modules
import scrollkeeper
import config


					# Defaults
dbxslfile = "stylesheets/docbook/html/docbook.xsl"

lang = locale.setlocale(locale.LC_ALL)	# hard code an ISO language code here to test it
#lang = "de"				# but it must match in scrollkeeper.py


BaseClass = BaseHTTPServer.BaseHTTPRequestHandler
ScrollKeeper = scrollkeeper.ScrollKeeper()



					# Kind of like make. Aging not implemented yet.
def FileCache(sourcefile, htmlfile, cmd):
	if not os.path.exists(htmlfile) or caching == 0:
		os.system(cmd)


class RequestHandler(BaseClass):
	"""
	Intercepts the HTTP requests and serves them.
	"""
	def do_GET(self):
		if fd := self.send_head():
			shutil.copyfileobj(fd, self.wfile)
			fd.close()
	
	def do_HEAD(self):
		fd = self.send_head()
		fd.close()
	
	def send_head(self):
		"""
		Send the requested page.
		"""
		if self.path in ["", "/", "/index.html"]:
			return self.send_Home()
		elif self.path == "/controls.html":
			return self.send_Controls()
		elif self.path == "/reset.html":
			return self.send_Reset()
		elif self.path == "/contents.html":
			return self.send_ContentsList()
		elif self.path =="/documents.html":
			return self.send_DocList()
		elif self.path == "/help.html":
			return self.send_Help()

		else:			# If not an internal page, it is a document or an
					#   image file being requested.
			uri = URI(self.path)

					# Serve a document
			if uri.Filename == "docid":
				return self.send_DocumentByID(uri.Parameter)
			else:
					# Try to serve a file
				return self.send_URI(uri)

	def send_Home(self):
		"""
		Send home page.
		"""
		FileCache(
		    "",
		    f"{htmlbase}index.html",
		    f"xsltproc {xsltparam} stylesheets/index.xsl stylesheets/index.xsl > {htmlbase}index.html",
		)
		return self.send_File(f"{htmlbase}index.html")
			
	def send_Help(self):
		"""
		Send help page.
		"""
		FileCache(
		    "",
		    f"{htmlbase}help.html",
		    f"xsltproc {xsltparam} stylesheets/help.xsl stylesheets/help.xsl > {htmlbase}help.html",
		)
		return self.send_File(f"{htmlbase}help.html")
			
	def send_Controls(self):
		"""
		Send controls page.
		"""
		FileCache(
		    "",
		    f"{htmlbase}controls.html",
		    f"xsltproc {xsltparam} stylesheets/controls.xsl stylesheets/controls.xsl > {htmlbase}controls.html",
		)
		return self.send_File(f"{htmlbase}controls.html")

	def send_Reset(self):
		"""
		Reset cache and send reset page.
		"""
		os.system(f"rm -rf {htmlbase}*")
		FileCache(
		    "",
		    f"{htmlbase}reset.html",
		    f"xsltproc {xsltparam} stylesheets/reset.xsl stylesheets/reset.xsl > {htmlbase}reset.html",
		)
		return self.send_File(f"{htmlbase}reset.html")

	def send_ContentsList(self):
		"""
		Send table of contents.
		"""
		contents_list = commands.getoutput(f"scrollkeeper-get-content-list {lang}")
		FileCache(
		    contents_list,
		    f"{htmlbase}contents.html",
		    f"xsltproc {xsltparam} stylesheets/contents.xsl {contents_list} > {htmlbase}contents.html",
		)
		return self.send_File(f"{htmlbase}contents.html")

	def send_DocList(self):
		"""
		Send alphabetical document list.
		"""
		contents_list = commands.getoutput(f"scrollkeeper-get-content-list {lang}")
		FileCache(
		    contents_list,
		    f"{htmlbase}documents.html",
		    f"xsltproc {xsltparam} stylesheets/documents.xsl {contents_list} > {htmlbase}documents.html",
		)
		return self.send_File(f"{htmlbase}documents.html")

	def send_DocumentByID(self, docid):
		"""
		Send a document.
		"""
		document = ScrollKeeper.DocumentByID(docid)
		if not document:
			text = "Error: ScrollServer couldn't find document number " + docid
			return self.send_Text(text)

					# Determine files and paths to read and write
		xmlfile = document.SourceFile
		xmlpath =  os.path.dirname(xmlfile)
		htmlpath = htmlbase + docid
		htmlfile = f"{htmlpath}/index.html"

		FileCache("", htmlpath, f"mkdir {htmlpath}")

		if document.Format == "text/sgml":
			FileCache(
			    xmlfile,
			    htmlfile,
			    f"xsltproc --docbook {xsltparam} {dbxslfile} {xmlfile} > {htmlfile}",
			)

						# Symbolic links to the files in source directory
						#   Required for efficient subsequent image requests
		os.system(f"ln -s --target-directory={htmlpath} {xmlpath}/*")
		return self.send_File(htmlfile)

	def send_URI(self, uri):
		"""
		Send some external file or image request.
		"""
		filename = f"{uri.Path}/{uri.Filename}"
		if os.path.isfile(filename):
			return self.send_File(filename)

					# Adjust relative links using referer
		referer = self.headers.getheader("Referer")
		refuri = URI(referer)
		if refuri.Filename == "docid":
			document = ScrollKeeper.DocumentByID(refuri.Parameter)
			filename = htmlbase + document.ID + "/" + uri.Path + "/" + uri.Filename
			return self.send_File(filename)
		else:
			text = f"Unrecognized request: {uri.Filename}"
			return self.send_Text(text)

	def send_File(self, filename):
		"""
		Send the contents of a file.
		"""
					# Extract extension, guess if missing
					#   Due to missing file extensions in some current
					#   ScrollKeeper data.
		temp = string.split(filename, ".")
		if len(temp) > 1:
			fileext = temp[1]
		else:
			if os.path.isfile(f"{filename}.png"):
				fileext = "png"
			elif os.path.isfile(f"{filename}.jpeg"):
				fileext = "jpeg"
			if os.path.isfile(f"{filename}.jpg"):
				fileext = "jpg"
			if os.path.isfile(f"{filename}.gif"):
				fileext = "gif"
			if fileext:
				filename += f".{fileext}"
				
							# Determine mimetype from extension
		if fileext in ["html", "htm"]:
			mimetype = "text/html"
		elif fileext == "png":
			mimetype = "image/png"
		elif fileext == "gif":
			mimetype = "image/gif"
		elif fileext in ["jpg", "jpeg"]:
			mimetype = "image/jpeg"
		elif fileext == "css":
			mimetype = "text/css"
		else:
			mimetype = "text/plain"

					# Send file if found, or error message
		if os.path.isfile(filename):
			fd = open(filename, 'r')
			filesize = os.fstat(fd.fileno())[stat.ST_SIZE]
			self.send_response(200)
			self.send_header("Content-type", mimetype)
			self.send_header("Content-length", filesize)
			self.end_headers()
			return fd
		return self.send_Text(f"Unrecognized file: {filename}")

	
	def send_Text(self, text):
		"""
		Send a text message.
		"""
		self.send_response(200)
		self.send_header("Content-type", "text/plain")
		self.send_header("Content-length", len(text))
		self.end_headers()
		return StringIO.StringIO(text)


def ScrollServer():
	"""
	Initialize the server.
	"""
	configDict = config.parseConfig()
	if configDict['help']:
		# Don't start the server if the user only wants help.
		sys.exit()
	global htmlbase, caching, xsltparam
	htmlbase = configDict['cache-dir']
	caching = not configDict['disable-cache']
	if configDict['timing']:
		xsltparam = '--timing'
	else:
		xsltparam = ''
	interface = configDict['interface']
	port = configDict['port']

	print "ScrollServer v0.6 -- development version!"
	if caching:
		os.system("rm -rf " + htmlbase + "*")
	else:
		print '(Caching disabled)'
	if interface != '':
		print '(Listening on interface %s, port %s)' % (interface, port)
	else:
		print '(Listening on all interfaces, port %s)' % port
	server = BaseHTTPServer.HTTPServer((interface, port), RequestHandler)
	server.serve_forever()

if __name__ == '__main__':
	ScrollServer()

