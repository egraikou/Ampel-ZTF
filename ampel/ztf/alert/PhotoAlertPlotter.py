#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File:                Ampel-ZTF/ampel/ztf/alert/PhotoAlertPlotter.py
# Author:              valery brinnel <firstname.lastname@gmail.com>
# Date:                23.01.2018
# Last Modified Date:  13.06.2018
# Last Modified By:    mg <matteo.giomi@desy.de>

import gzip, io, os
import numpy as np
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy.time import Time
from matplotlib.colors import Normalize
from ampel.protocol.AmpelAlertProtocol import AmpelAlertProtocol


import logging
logger = None

class PhotoAlertPlotter:


	pp_colors = ["C2", "C3", "C1"]
	filter_names = ["ztf-g", "ztf-r", "ztf-i"]
	lc_marker_props = dict(marker="o", mec="0.7", ms=8, ecolor="0.7", ls="None")


	@staticmethod
	def get_cutout_numeric(alert: AmpelAlertProtocol, which, scaler = None):
		"""
		parse the cutout tstamp into numeric data

		Parameters:
		----------

		which: `str`
			either 'cutoutScience', 'cutoutTemplate', or 'cutoutDiffernce'.

		scaler: `callable`
			function to scale/strecth the image to be applied to the data. Must
			accept and return a 2d numpy array.
		"""

		# TODO: check that alert is a DevPhotoAlert
		if alert.extra is None or 'cutouts' not in alert.extra or which not in alert.extra['cutouts']:
			return None
		stamp = alert.extra['cutouts'][which]
		with gzip.open(io.BytesIO(stamp), 'rb') as f:
			raw = fits.open(f)[0].data
			if scaler is not None:
				scaler(raw)		# TODO: some astropy.visualization stuff do not like this
			else:
				return raw


	def __init__(self, interactive=True, plot_dir=None, plot_name_tmpl="{objectId}.png", logger = None):
		"""
			init the plotter object in either interactive or save-plot-to-file mode.

			Parameters:
			-----------

				interactive: `bool`
					if True plots will be shown, else saved to file.

				plotdir: `str`
					path to directory where plots will be saved.
					Only useful if not interactive.

				plot_name_tmpl: `str`
					template string for creating file names. All the keys from alert avro
					for the candidate and its the latest photopoint can be used.
		"""

		if logger is None:
			logging.basicConfig(level = logging.INFO)
			self.logger = logging.getLogger(__name__)
		else:
			self.logger = logger

		self.interactive = interactive
		if self.interactive:
			self.logger.info("Initialized PhotoAlertPlotter in interactive mode.")
		else:
			if plot_dir is None:
				plot_dir = "./"
			elif not os.path.isdir(plot_dir):
				os.makedirs(plot_dir)
			self.plot_dir = plot_dir
			self.logger.info(
				"Initialized PhotoAlertPlotter in bash-mode. Plots will be saved to %s." % self.plot_dir)
		self.base_plot_name_tmpl = plot_name_tmpl


	def save_current_plot(self, alert: AmpelAlertProtocol, file_name_template, **kwargs):

		alert_props = {**alert.datapoints[0], 'objectId': alert.stock}
		fname = file_name_template.format(**alert_props)
		fname = os.path.join(self.plot_dir, fname)
		fig = plt.gcf()
		fig.savefig(fname, **kwargs)
		plt.close(fig)
		self.logger.info("current figure saved to %s" % fname)


	def exit(self, alert: AmpelAlertProtocol, fine_name_tag, ax_given, ax, **kwargs):
		"""
		depending on whether you are in interactive mode, and if an
		axes was given to the function, either show, save, or return axes.
		"""

		if ax_given:
			return ax
		elif self.interactive:
			plt.show()
			return ax
		else:
			fname_tmplt = fine_name_tag + self.base_plot_name_tmpl
			self.save_current_plot(alert, fname_tmplt, **kwargs)
			return None


	def scatter_plot(self, alert: AmpelAlertProtocol, p1, p2, ax = None, **kwargs):
		"""
		Make scatter plot of parameter p1 vs p2.

		Parameters:
		-----------
		p1[2]: `str`
			x[y]-axis parameter (ex: p1 = 'obs_date', p2 = 'magpsf' to plot lightcurve)

		ax: `matplotlib.pyplot.axes`
			axes used for plotting. If None, a new one will be created.

		kwargs:
			kwargs arguments passed to matplotlib.pyplot.scatter or matplotlib.pyplot.savefig.

		Returns:
		--------

			if ax is None, then return the axis created.
		"""

		ax_given = True
		if ax is None:
			ax = plt.axes()
			ax_given = False
		ax.scatter(*zip(*alert.get_tuples(p1, p2)), **kwargs)
		ax.set_xlabel(p1)
		ax.set_ylabel(p2)
		ax.grid(True)

		return self.exit(alert, "scatter_%s_%s" % (p1, p2), ax_given, ax, **kwargs)


	def plot_lc(self, alert: AmpelAlertProtocol, ax = None, time_format = 'datetime', **kwargs):
		"""
		plot lightcurve for transient: magpsf vs. jd
		"""

		# dectections
		mag, mag_err, jd, fid = [
			np.array(x) for x in zip(
				*alert.get_ntuples(
					["magpsf", "sigmapsf", "jd", "fid"],
					filters=[{'attribute': 'magpsf', 'operator': 'is not', 'value': None}]
				)
			)
		]

		has_ulim = False
		if r := alert.get_ntuples(
			["diffmaglim", "jd", "fid"],
			filters=[{'attribute': 'magpsf', 'operator': 'is', 'value': None}]
		):
			ul_mag_lim, ul_jd, ul_fid = [np.array(x) for x in zip(*r)]
			has_ulim = True

		# convert the time
		if time_format == 'datetime':
			time = Time(jd, format='jd').datetime
			if has_ulim:
				ul_time = Time(ul_jd, format='jd').datetime
		elif time_format == 'jd':
			time = Time(jd, format='jd')
			if has_ulim:
				ul_time = Time(ul_jd, format='jd')
		else:
			raise ValueError("got %s as value for 'time_format'. Available are 'jd' and 'datetime'")

		# plot lightcurve points
		ax_given = True
		if ax is None:
			ax = plt.axes()
			ax_given = False

		ax.invert_yaxis()
		for ifilter in [1, 2, 3]:
			label = "magpsf %s" % self.__class__.filter_names[ifilter - 1]
			color = self.__class__.pp_colors[ifilter - 1]

			# plot detctecions
			f_mask = (fid == ifilter)
			if any(f_mask):
				ax.errorbar(
					x=time[f_mask], y=mag[f_mask], xerr=None, yerr=mag_err[f_mask],
					label=label, mfc=color, **self.__class__.lc_marker_props)

			# plot ulims if available
			if has_ulim:
				ul_f_mask = (ul_fid == ifilter)
				if any(ul_f_mask):
					ax.errorbar(
						ul_time[ul_f_mask], ul_mag_lim[ul_f_mask], yerr=0.2, lolims=True,
						color=color, ls="None", label="_no_legend_")

		# single-out latest detection
		ax.errorbar(
			time[0], mag[0], xerr=None, yerr=mag_err[0],
			marker="D", color=self.__class__.pp_colors[fid[0] - 1], ms=8, ecolor="0.7",
			ls="None", label="_no_legend_")

		# beautify
		ax.legend(loc="best")
		ax.set_xlabel("Date", fontsize="large")
		ax.set_ylabel("mag (magpsf)", fontsize="large")
		ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
		ax.xaxis.set_tick_params(rotation=45)

		return self.exit(alert, "lc_", ax_given, ax, **kwargs)


	def plot_cutout(self, alert: AmpelAlertProtocol, which, ax = None, cb = False, scaler = None, **kwargs):
		""" plot image cutout """

		ax_given = True
		if ax is None:
			ax = plt.axes()
			ax_given = False

		img_data = PhotoAlertPlotter.get_cutout_numeric(alert, which, scaler)
		if img_data is not None:
			mask = np.isfinite(img_data)
			im = ax.imshow(
				img_data,
				norm=Normalize(*np.percentile(img_data[mask], [0.5, 99.5])),
				aspect="auto"
			)
			if cb:
				plt.colorbar(im, ax=ax)
		else:
			ax.text(0.5, 0.5, 'no data', va='center', ha='center', transform=ax.transAxes)
		ax.set_title(which)
		ax.set_yticks([])
		ax.set_xticks([])

		# return show
		return self.exit(alert, which + "_", ax_given, ax, **kwargs)


	@staticmethod
	def plot_ps1_cutout(alert, ax = None):
		pass


	def summary_plot(self, alert: AmpelAlertProtocol, ps1_cutout=False, **kwargs):
		"""
		create a summary plot for the given alert. This includes
		the three cutouts (ref, sci, diff), the light curve, and
		some printouts of several alert parameters.
		"""

		# set figure and axis
		plt.close('all')
		fig = plt.figure(figsize=[9, 5])
		ref, width, heigh = 0.1, 0.15, 0.25
		span = 0.05
		ypos = 0.65
		cutout_axes = {
			'cutoutScience': fig.add_axes([ref, ypos, width, heigh]),
			'cutoutTemplate': fig.add_axes([ref + (width + span), ypos, width, heigh]),
			'cutoutDifference': fig.add_axes([ref + (width + span) * 2, ypos, width, heigh])
		}
		axlc = fig.add_axes([ref, 0.1, (width + span) * 2 + width, 0.5])
		if ps1_cutout:
			fig.add_axes([ref + (width + span * 1.5) * 3, ypos, width, heigh])

		# plot the cutouts
		for which in ('cutoutScience', 'cutoutTemplate', 'cutoutDifference'):
			self.plot_cutout(alert, which, ax=cutout_axes[which])

		# plot the lightcurve
		self.plot_lc(alert, ax=axlc)

		# add text
		candidate = alert.datapoints[0]
		info = []
		for k in ["rb", "fwhm", "nbad", "elong", "isdiffpos", "ssdistnr"]:
			try:
				info.append("%s : %.3f" % (k, candidate.get(k, np.nan)))
			except Exception:
				info.append("%s : %s" % (k, candidate.get(k)))
		for kk in ["objectidps", "sgscore", "distpsnr", "srmag"]:
			for k in [k for k in candidate.keys() if kk in k]:
				info.append("%s : %.2f" % (k, float(candidate.get(k, np.nan))))
		fig.text(0.68, 0.6, " \n".join(info), va="top", fontsize="medium", color="0.3")
		fig.text(0.01, 0.99, alert.stock, fontsize="x-large", color="k", va="top", ha="left")

		# now go back to previous state
		if self.interactive:
			plt.show(fig)
		else:
			self.save_current_plot(alert, "summary_" + self.base_plot_name_tmpl, **kwargs)
