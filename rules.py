#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import re
from SCons.Builder import Builder
from SCons.Script import AddOption, GetOption
import SCons.Util
import subprocess
import sys

def RunUnitTest(env, target, source):
    import subprocess
    test = str(source[0].abspath)
    logfile = open(target[0].abspath, 'w')
    cmd = [test]
    ShEnv = {env['ENV_SHLIB_PATH']: 'build/lib',
             'HEAPCHECK': 'normal',
             'PPROF_PATH': 'build/bin/pprof',
             'DB_ITERATION_TO_YIELD': '1',
             'PATH': os.environ['PATH']}
    code = subprocess.call(cmd, stdout=logfile, stderr=logfile, env=ShEnv)
    if code == 0:
        print test + '\033[94m' + " PASS" + '\033[0m'
    else:
        logfile.write('[  FAILED  ] ')
        if code < 0:
            logfile.write('Terminated by signal: ' + str(-code) + '\n')
        else:
            logfile.write('Program returned ' + str(code) + '\n') 
        print test + '\033[91m' + " FAIL" + '\033[0m'

def TestSuite(env, target, source):
    for test in source:
        log = test[0].abspath + '.log'
        cmd = env.Command(log, test, RunUnitTest)
        env.AlwaysBuild(cmd)
        env.Alias(target, cmd)
    return target

def PyTestSuite(env, target, source):
    for test in source:
        log = test + '.log'
        cmd = env.Command(log, test, RunUnitTest)
        env.AlwaysBuild(cmd)
        env.Alias(target, cmd)
    return target

def UnitTest(env, name, sources):
    test_env = env.Clone()
    if sys.platform != 'darwin' and env.get('OPT') != 'coverage':
        test_env.Append(LIBPATH = '#/build/lib')
        test_env.Append(LIBS = ['tcmalloc'])
    return test_env.Program(name, sources)

def GenerateBuildInfoCode(env, target, source, path):
    try:
        build_user = os.environ['USER']
    except KeyError:
        build_user = "unknown"

    try:
        build_host = os.environ['HOSTNAME']
    except KeyError:
        build_host = "unknown"

    # Fetch Time in UTC
    import datetime
    build_time = unicode(datetime.datetime.utcnow())

    # Fetch git version
    p = subprocess.Popen('git log --oneline | head -1 | awk \'{ print $1 }\'',
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell='True')
    build_git_info, err = p.communicate()
    build_git_info = build_git_info.strip()

    # Fetch build version
    file_path = env.Dir('#').abspath + '/src/base/version.info'
    f = open(file_path)
    build_version = (f.readline()).strip()

    # build json string containing build information
    build_info = "{\\\"build-info\\\" : [{\\\"build-version\\\" : \\\"" + str(build_version) + "\\\", \\\"build-time\\\" : \\\"" + str(build_time) + "\\\", \\\"build-user\\\" : \\\"" + build_user + "\\\", \\\"build-hostname\\\" : \\\"" + build_host + "\\\", \\\"build-git-ver\\\" : \\\"" + build_git_info + "\\\", "
    h_code = "#ifndef ctrlplane_buildinfo_h\n#define ctrlplane_buildinfo_h\n\n#include <string>\nextern const std::string BuildInfo;\n\n#endif // ctrlplane_buildinfo_h\n"
    cc_code ="#include <buildinfo.h>\n\nconst std::string BuildInfo = \""+ build_info + "\";\n"
    h_file = file(path + '/buildinfo.h', 'w')
    h_file.write(h_code)
    h_file.close()

    cc_file = file(path + '/buildinfo.cc', 'w')
    cc_file.write(cc_code)
    cc_file.close()
    return 
#end GenerateBuildInfoCode

def GenerateBuildInfoPyCode(env, target, source, path):
    import os
    import subprocess

    try:
        build_user = os.environ['USER']
    except KeyError:
        build_user = "unknown"

    try:
        build_host = os.environ['HOSTNAME']
    except KeyError:
        build_host = "unknown"

    # Fetch Time in UTC
    import datetime
    build_time = unicode(datetime.datetime.utcnow())

    # Fetch git version
    p = subprocess.Popen('git log --oneline | head -1 | awk \'{ print $1 }\'',
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell='True')
    build_git_info, err = p.communicate()
    build_git_info = build_git_info.strip()

    # Fetch build version
    file_path = env.Dir('#').abspath + '/src/base/version.info'
    f = open(file_path)
    build_version = (f.readline()).strip()

    # build json string containing build information
    build_info = "{\\\"build-info\\\" : [{\\\"build-version\\\" : \\\"" + str(build_version) + "\\\", \\\"build-time\\\" : \\\"" + str(build_time) + "\\\", \\\"build-user\\\" : \\\"" + build_user + "\\\", \\\"build-hostname\\\" : \\\"" + build_host + "\\\", \\\"build-git-ver\\\" : \\\"" + build_git_info + "\\\", "
    py_code ="build_info = \""+ build_info + "\";\n"
    if not os.path.exists(path):
        os.makedirs(path)
    py_file = file(path + '/buildinfo.py', 'w')
    py_file.write(py_code)
    py_file.close()

    return 
#end GenerateBuildInfoPyCode

def Basename(path):
    return path.rsplit('.', 1)[0]

# ExtractCpp Method
def ExtractCppFunc(env, filelist):
    CppSrcs = []
    for target in filelist:
        fname = str(target)
        ext = fname.rsplit('.', 1)[1]
        if ext == 'cpp':
            CppSrcs.append(fname)
    return CppSrcs

# ExtractC Method
def ExtractCFunc(env, filelist):
    CSrcs = []
    for target in filelist:
        fname = str(target)
        ext = fname.rsplit('.', 1)[1]
        if ext == 'c':
            CSrcs.append(fname)
    return CSrcs

# ExtractHeader Method
def ExtractHeaderFunc(env, filelist):
    Headers = []
    for target in filelist:
        fname = str(target)
        ext = fname.rsplit('.', 1)[1]
        if ext == 'h':
            Headers.append(fname)
    return Headers


class SandeshWarning(SCons.Warnings.Warning):
    pass

class SandeshCodeGeneratorError(SandeshWarning):
    pass

# SandeshGenOnlyCpp Methods
def SandeshOnlyCppBuilder(target, source, env):
    opath = str(target[0]).rsplit('/',1)[0] + "/"
    sname = str(target[0]).rsplit('/',1)[1].rsplit('_',1)[0]
    sandeshcmd = env.Dir(env['TOP_BIN']).abspath + '/sandesh'
    code = subprocess.call(sandeshcmd + ' --gen cpp -I src/ -out ' + 
                           opath + " " + str(source[0]), shell=True)
    if code != 0:
        raise SCons.Errors.StopError(SandeshCodeGeneratorError,
                                     'Sandesh code generation failed')
    cname = sname + "_html.cpp"
    os.system("echo \"int " + sname + "_marker = 0;\" >> " + opath + cname)

def SandeshSconsEnvOnlyCppFunc(env):
    onlycppbuild = Builder(action = SandeshOnlyCppBuilder)
    env.Append(BUILDERS = {'SandeshOnlyCpp' : onlycppbuild})

def SandeshGenOnlyCppFunc(env, file):
    SandeshSconsEnvOnlyCppFunc(env)
    suffixes = ['_types.h',
        '_types.cpp',
        '_constants.h',
        '_constants.cpp',
        '_html.cpp']
    basename = Basename(file)
    targets = map(lambda suffix: basename + suffix, suffixes)
    env.Depends(targets, '#/build/bin/sandesh')
    return env.SandeshOnlyCpp(targets, file)

# SandeshGenCpp Methods
def SandeshCppBuilder(target, source, env):
    opath = str(target[0]).rsplit('/',1)[0] + "/"
    sname = str(target[0]).rsplit('/',1)[1].rsplit('_',1)[0]
    sandeshcmd = env.Dir(env['TOP_BIN']).abspath + '/sandesh'
    code = subprocess.call(sandeshcmd + ' --gen cpp --gen html -I src/ -out '
                           + opath + " " + str(source[0]), shell=True)
    if code != 0:
        raise SCons.Errors.StopError(SandeshCodeGeneratorError, 
                                     'Sandesh code generation failed')
    tname = sname + "_html_template.cpp"
    hname = sname + ".xml"
    cname = sname + "_html.cpp"
    if not env.Detect('xxd'):
        raise SCons.Errors.StopError(SandeshCodeGeneratorError,
                                     'xxd not detected on system')
    os.system("echo \"namespace {\"" + " >> " + opath + cname)
    os.system("(cd " + opath + " ; xxd -i " + hname + " >> " + cname + " )")
    os.system("echo \"}\"" + " >> " + opath + cname)
    os.system("cat " + opath + tname + " >> " + opath + cname)

def SandeshSconsEnvCppFunc(env):
    cppbuild = Builder(action = SandeshCppBuilder)
    env.Append(BUILDERS = {'SandeshCpp' : cppbuild})

def SandeshGenCppFunc(env, file):
    SandeshSconsEnvCppFunc(env)
    suffixes = ['_types.h',
        '_types.cpp',
        '_constants.h',
        '_constants.cpp',
        '_html.cpp']
    basename = Basename(file)
    targets = map(lambda suffix: basename + suffix, suffixes)
    env.Depends(targets, '#/build/bin/sandesh')
    return env.SandeshCpp(targets, file)

# SandeshGenC Methods
def SandeshCBuilder(target, source, env):
    opath = str(target[0]).rsplit('gen-c',1)[0]
    sandeshcmd = env.Dir(env['TOP_BIN']).abspath + '/sandesh'
    code = subprocess.call(sandeshcmd + ' --gen c -o ' + opath +
                           ' ' + str(source[0]), shell=True) 
    if code != 0:
        raise SCons.Errors.StopError(SandeshCodeGeneratorError, 
                                     'Sandesh code generation failed')
            
def SandeshSconsEnvCFunc(env):
    cbuild = Builder(action = SandeshCBuilder)
    env.Append(BUILDERS = {'SandeshC' : cbuild})

def SandeshGenCFunc(env, file):
    SandeshSconsEnvCFunc(env)
    suffixes = ['_types.h', '_types.c']
    basename = Basename(file)
    targets = map(lambda suffix: 'gen-c/' + basename + suffix, suffixes)
    env.Depends(targets, '#/build/bin/sandesh')
    return env.SandeshC(targets, file)

# SandeshGenPy Methods
def SandeshPyBuilder(target, source, env):
    opath = str(target[0]).rsplit('/',1)[0] 
    py_opath = opath.rsplit('/',1)[0] + '/'
    sandeshcmd = env.Dir(env['TOP_BIN']).abspath + '/sandesh'
    code = subprocess.call(sandeshcmd + ' --gen py:new_style -I src/ -out ' + \
        py_opath + " " + str(source[0]), shell=True)
    if code != 0:
        raise SCons.Errors.StopError(SandeshCodeGeneratorError, 
                                     'Sandesh Compiler Failed')
    html_opath = opath + '/'
    code = subprocess.call(sandeshcmd + ' --gen html -I src/ -out ' + \
        html_opath + " " + str(source[0]), shell=True)
    if code != 0:
        raise SCons.Errors.StopError(SandeshCodeGeneratorError, 
                                     'Sandesh code generation failed')

def SandeshSconsEnvPyFunc(env):
    pybuild = Builder(action = SandeshPyBuilder)
    env.Append(BUILDERS = {'SandeshPy' : pybuild})

def SandeshGenPyFunc(env, path, target=''):
    SandeshSconsEnvPyFunc(env)
    modules = [
        '__init__.py',
        'constants.py',
        'ttypes.py',
        'http_request.py']
    basename = Basename(path)
    path_split = basename.rsplit('/',1)
    if len(path_split) == 2:
        mod_dir = path_split[1] + '/'
    else:
        mod_dir = path_split[0] + '/'
    targets = map(lambda module: target + 'gen_py/' + mod_dir + module, modules)
    env.Depends(targets, '#/build/bin/sandesh')
    return env.SandeshPy(targets, path)

# ThriftGenCpp Methods
ThriftServiceRe = re.compile(r'service\s+(\S+)\s*{', re.M)
def ThriftServicesFunc(node):
    contents = node.get_text_contents()
    return ThriftServiceRe.findall(contents)

def ThriftSconsEnvFunc(env, async):
    opath = env.Dir('.').abspath
    thriftcmd = env.Dir(env['TOP_BIN']).abspath + '/thrift'
    if async:
        lstr = thriftcmd + ' --gen cpp:async -o ' + opath + ' $SOURCE'
    else:
        lstr = thriftcmd + ' --gen cpp -o ' + opath + ' $SOURCE'
    cppbuild = Builder(action = lstr)
    env.Append(BUILDERS = {'ThriftCpp' : cppbuild})

def ThriftGenCppFunc(env, file, async):
    ThriftSconsEnvFunc(env, async)
    suffixes = ['_types.h', '_constants.h', '_types.cpp', '_constants.cpp']
    basename = Basename(file)
    base_files = map(lambda s: 'gen-cpp/' + basename + s, suffixes)
    services = ThriftServicesFunc(env.File(file))
    service_cfiles = map(lambda s: 'gen-cpp/' + s + '.cpp', services)
    service_hfiles = map(lambda s: 'gen-cpp/' + s + '.h', services)
    targets = base_files + service_cfiles + service_hfiles
    env.Depends(targets, '#/build/bin/thrift')
    return env.ThriftCpp(targets, file)

def IFMapBuilderCmd(source, target, env, for_signature):
    output = Basename(source[0].abspath)
    return './tools/generateds/generateDS.py -f -g ifmap-backend -o %s %s' % (output, source[0])

def IFMapTargetGen(target, source, env):
    suffixes = ['_types.h', '_types.cc', '_parser.cc',
                '_server.cc', '_agent.cc']
    basename = Basename(source[0].abspath)
    targets = map(lambda x: basename + x, suffixes)
    return targets, source

def CreateIFMapBuilder(env):
    builder = Builder(generator = IFMapBuilderCmd,
                      src_suffix = '.xsd',
                      emitter = IFMapTargetGen)
    env.Append(BUILDERS = { 'IFMapAutogen' : builder})
    
def TypeBuilderCmd(source, target, env, for_signature):
    output = Basename(source[0].abspath)
    return './tools/generateds/generateDS.py -f -g type -o %s %s' % (output, source[0])

def TypeTargetGen(target, source, env):
    suffixes = ['_types.h', '_types.cc', '_parser.cc']
    basename = Basename(source[0].abspath)
    targets = map(lambda x: basename + x, suffixes)
    return targets, source

def CreateTypeBuilder(env):
    builder = Builder(generator = TypeBuilderCmd,
                      src_suffix = '.xsd',
                      emitter = TypeTargetGen)
    env.Append(BUILDERS = { 'TypeAutogen' : builder})

def SetupBuildEnvironment(env):
    AddOption('--optimization', dest = 'opt',
              action='store', default='debug',
              choices = ['debug', 'production', 'coverage', 'profile'],
              help='optimization level: [debug|production|coverage|profile]')

    AddOption('--target', dest = 'target',
              action='store',
              choices = ['i686', 'x86_64'])

    env['OPT'] = GetOption('opt')
    env['TARGET_MACHINE'] = GetOption('target')

    if sys.platform == 'darwin':
        env['ENV_SHLIB_PATH'] = 'DYLD_LIBRARY_PATH'
    else:
        env['ENV_SHLIB_PATH'] = 'LD_LIBRARY_PATH'

    if env.get('TARGET_MACHINE') == 'i686':
        env.Append(CCFLAGS = '-march=' + arch)

    env['TOP_BIN'] = '#build/bin'
    env['TOP_INCLUDE'] = '#build/include'
    env['TOP_LIB'] = '#build/lib'

    opt_level = env['OPT']
    if opt_level == 'production':
        env.Append(CCFLAGS = '-O3')
        env['TOP'] = '#build/production'
    elif opt_level == 'debug':
        env.Append(CCFLAGS = ['-g', '-O0', '-DDEBUG'])
        env['TOP'] = '#build/debug'
    elif opt_level == 'profile':
        # Enable profiling through gprof
        env.Append(CCFLAGS = ['-g', '-O3', '-DDEBUG', '-pg'])
        env.Append(LINKFLAGS = ['-pg'])
        env['TOP'] = '#build/profile'
    elif opt_level == 'coverage':
        env.Append(CCFLAGS = ['-g', '-O0', '--coverage'])
        env['TOP'] = '#build/coverage'
        env.Append(LIBS = 'gcov')

    env.Append(BUILDERS = {'PyTestSuite': PyTestSuite })
    env.Append(BUILDERS = {'TestSuite': TestSuite })
    env.Append(BUILDERS = {'UnitTest': UnitTest})
    env.Append(BUILDERS = {'GenerateBuildInfoCode': GenerateBuildInfoCode})
    env.Append(BUILDERS = {'GenerateBuildInfoPyCode': GenerateBuildInfoPyCode})

    env.AddMethod(ExtractCppFunc, "ExtractCpp")
    env.AddMethod(ExtractCFunc, "ExtractC")
    env.AddMethod(ExtractHeaderFunc, "ExtractHeader")    
    env.AddMethod(SandeshGenOnlyCppFunc, "SandeshGenOnlyCpp")
    env.AddMethod(SandeshGenCppFunc, "SandeshGenCpp")
    env.AddMethod(SandeshGenCFunc, "SandeshGenC")
    env.AddMethod(SandeshGenPyFunc, "SandeshGenPy")
    env.AddMethod(ThriftGenCppFunc, "ThriftGenCpp")
    CreateIFMapBuilder(env)
    CreateTypeBuilder(env)
# SetupBuildEnvironment