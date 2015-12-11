# Copyright 2015 IBM Corporation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Memory bandwidth monitor based on virt driver to retrieve Memory bw utilization
"""

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import timeutils

from nova.compute.monitors import base
from nova import exception
from nova.i18n import _LE
from nova import objects

CONF = cfg.CONF
CONF.import_opt('compute_driver', 'nova.virt.driver')
LOG = logging.getLogger(__name__)


class Monitor(base.MemoryBandwidthMonitorBase):

    def __init__(self, compute_manager):
        super(Monitor, self).__init__(compute_manager)
        self.source = CONF.compute_driver
        self.driver = self.compute_manager.driver
        self.max_mem_bw = self.driver.get_max_memory_bw()
        self._prev_count = {}
        self._data = {}

    def populate_metric_object(self, name, metric_object):
        self._update_data(metric_obj)
        metric_object.numa_membw_values = self._data[name]
        metric_object.timestamp = self._data['timestamp']
        metric_object.source = self.source

    def _update_data(self, metric_object):
        # Don't allow to call this function so frequently (<= 1 sec)
        now = timeutils.utcnow()
        time_diff = 0
        if self._data.get("timestamp") is not None:
            delta = now - self._data.get("timestamp")
            if delta.seconds <= 1:
                return
            else:
                time_diff = delta.seconds
        self._data = {}
        self._data["timestamp"] = now
        try:
            if metric_object.name == "numa.membw.current":
                self.driver.get_current_memory_bw(metric_obj)
                mem_counter = metric_obj.numa_membw_values
                if time_diff > 0:
                    current_mem_bw = {}
                    for node in mem_counter.keys():
                        numa_curr_count = mem_counter[node]
                        numa_prev_count = self._prev_count.get(node, 0)
                        if numa_curr_count - numa_prev_count > 0:
                            bw = numa_curr_count - numa_prev_count / time_diff
                        current_mem_bw[node] = bw
                metric_obj.numa_membw_values = current_mem_bw
            elif metric_object.name == "numa.membw.max":
                metric_obj.numa_membw_values = self.max_mem_bw
            self._prev_count = mem_counter.copy()
        except (NotImplementedError, TypeError, KeyError):
            LOG.exception(_LE("Not all properties needed are implemented "
                              "in the compute driver"))
            raise exception.ResourceMonitorError(
                monitor=self.__class__.__name__)
