/*
 * Copyright 2017-present Open Networking Foundation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.opencord.cordvtn.cli;

import org.apache.karaf.shell.commands.Argument;
import org.apache.karaf.shell.commands.Command;
import org.apache.karaf.shell.commands.Option;
import org.onosproject.cli.AbstractShellCommand;
import org.opencord.cordvtn.api.core.ServiceNetworkAdminService;

/**
 * Synchronizes network states with OpenStack Neutron.
 * This command can be used to actively synchronize Neutron network with VTN
 * service network.
 */
@Command(scope = "onos", name = "cordvtn-sync-neutron-states",
        description = "Synchronizes network states with Neutron")
public class CordVtnSyncNeutronStatesCommand extends AbstractShellCommand {

    @Option(name = "-c", aliases = "--config", description = "Use connection values from config",
            required = false, multiValued = false)
    private boolean config = false;

    @Argument(index = 0, name = "endpoint", description = "OpenStack service endpoint",
            required = true, multiValued = false)
    private String endpoint = null;

    @Argument(index = 1, name = "tenant", description = "OpenStack admin tenant name",
            required = true, multiValued = false)
    private String tenant = null;

    @Argument(index = 2, name = "user", description = "OpenStack admin user name",
            required = true, multiValued = false)
    private String user = null;

    @Argument(index = 3, name = "password", description = "OpenStack admin user password",
            required = true, multiValued = false)
    private String password = null;

    @Override
    protected void execute() {
        ServiceNetworkAdminService snetService =
                AbstractShellCommand.get(ServiceNetworkAdminService.class);

        print("Synchronizing neutron state...");
        if (config) {
            snetService.syncNeutronState();
        } else {
            snetService.syncNeutronState(endpoint, tenant, user, password);
        }
    }
}
