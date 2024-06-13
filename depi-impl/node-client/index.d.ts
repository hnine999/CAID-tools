import * as grpc from '@grpc/grpc-js';
import * as depi from './src/pbs/depi_pb';
import { DepiClient } from './src/pbs/depi_grpc_pb';
import { addAsyncMethods } from './src/pbs/addAsyncMethods';
import depiUtils, { DepiSession } from './src/depiUtils';
import DepiExtensionApi, { TokenLoginData } from './src/depiExtensionApi';

import {
    ResourcePattern,
    Resource,
    ResourceRef,
    ResourceGroupRef,
    ResourceGroup,
    ResourceLinkRef,
    ResourceLink,
    LinkPattern,
    ResourceChange,
    ChangeType,
} from './src/@types/depi';

export {
    grpc,
    depi,
    DepiClient,
    addAsyncMethods,
    depiUtils,
    DepiExtensionApi,
    TokenLoginData,
    DepiSession,
    ResourcePattern,
    Resource,
    ResourceRef,
    ResourceGroupRef,
    ResourceGroup,
    ResourceLinkRef,
    ResourceLink,
    LinkPattern,
    ResourceChange,
    ChangeType,
};