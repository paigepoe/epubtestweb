import argparse
import os
import yaml
import epub_parser
import import_testsuite
import epub_id_check
from testsuite_app import models
from testsuite_app.models import common
from testsuite_app import helper_functions
from testsuite_app import export_data
from random import randrange
from django.contrib.sessions.models import Session
from testsuite_app.models import UserProfile
from datetime import datetime


def print_testsuite():
    rs = models.ReadingSystem.objects.get(id=1)
    res = helper_functions.get_results_as_nested_categories(rs)
    for r in res:
        helper_functions.print_item_summary(r)

# import testsuites from the YAML configuration file
def add_testsuites(sourcedir, config_file):
    norm_sourcedir = os.path.normpath(sourcedir)
    norm_config_file = os.path.normpath(config_file)
    print "\nProcessing {0} (config = {1})".format(norm_sourcedir, norm_config_file)

    testsuites = yaml.load(open(norm_config_file).read())['TestSuites']

    for ts in testsuites:
        add_testsuite(ts, norm_sourcedir)

# look at each referenced epub in the testsuite config section
def add_testsuite(config_section, sourcedir):
    yaml_categories = config_section['Categories']
    testsuite_type = common.TESTSUITE_TYPE_DEFAULT
    if config_section['Type'] == "Accessibility": #TODO formalize this enum
        testsuite_type = common.TESTSUITE_TYPE_ACCESSIBILITY
    old_testsuite = models.TestSuite.objects.get_most_recent_testsuite_of_type(testsuite_type)
    testsuite = import_testsuite.create_testsuite(testsuite_type)

    epub_id_checker = epub_id_check.EpubIdCheck()
    epub_id_checker.process_epubs(sourcedir)
    for cat in yaml_categories:
        new_category = import_testsuite.add_category('1', cat['Name'], "", None, testsuite, None)
        for epubid in cat['EpubIds']:
            filename = epub_id_checker.get_filename_for_id(epubid)
            epubparser = epub_parser.EpubParser()
            epubparser.parse(filename, new_category, testsuite, cat['CategoryDisplayDepthLimit'])

    num_tests = models.Test.objects.filter(testsuite = testsuite).count()
    print "This testsuite contains {0} tests".format(num_tests)
    if old_testsuite != None:
        import_testsuite.migrate_data(old_testsuite)
    else:
        print "Nothing to migrate"
    print "Done importing testsuite."

def add_user(username, email, password, firstname, lastname):
    user = models.UserProfile.objects.create_user(username, email, password)
    user.first_name = firstname
    user.last_name = lastname
    user.is_superuser = False
    user.save()
    return user

def add_rs(name):
    user = models.UserProfile.objects.all()[0]
    rs = models.ReadingSystem(
        locale = "US",
        name = name,
        operating_system = "OSX",
        notes = "NOTES",
        version = "1.0",
        user = user,
    )
    rs.save() 
    
    return rs

def export(outfile):
    xmldoc = export_data.export_all_current_reading_systems(None)
    xmldoc.write(outfile)
    print "Data exported to {0}".format(outfile)

def listrs():
    rses = models.ReadingSystem.objects.all()
    for rs in rses:
        print "{0}: {1}".format(rs.name, rs.pk)

def geneval(rspk, testsuite_type):
    try:
        rs = models.ReadingSystem.objects.get(id=rspk)
    except models.ReadingSystem.DoesNotExist:
        return
    testsuite = None
    if testsuite_type == "DEFAULT":
        testsuite = models.TestSuite.objects.get_most_recent_testsuite()
    else:
        testsuite = models.TestSuite.objects.get_most_recent_accessibility_testsuite()
    result_set = models.ResultSet.objects.create_result_set(rs, testsuite, rs.user)
    result_set.save()
    if testsuite_type == "ACCESSIBILITY":
        result_set.add_metadata("AT123", common.INPUT_TYPE_KEYBOARD, False, False)
    # generate result data
    results = result_set.get_results()
    for r in results:
        r.result = str(randrange(1, 3))
        r.save()


def getemails():
    users = models.UserProfile.objects.all()
    # SELECT DISTINCT on fields not supported by SQLite backend so we have to do it manually
    # luckily this is an isolated case with a small dataset, and one where we can afford to be a little slow
    distinct_emails = []
    for u in users:
        if u.email.lower() not in distinct_emails:
            distinct_emails.append(u.email.lower())
    emails = ", ".join(distinct_emails)
    print emails

def listusers():
    users = models.UserProfile.objects.all()
    for u in users:
        print "{0}\t\t\t\t{1} {2}".format(u.username, u.first_name.encode('utf-8'), u.last_name.encode('utf-8'))

# def integrity_check():
#     "make sure that all RS evals have the right number of tests and score entries"
#     report = {} 
#     rses = models.ReadingSystem.objects.all()
#     for rs in rses:
#         report[rs] = {"results": "ok", "scores": "ok"}
#         print "Checking Reading System: {0} (ID = {1})".format(rs.name, rs.pk)
#         evaluations = models.Evaluation.objects.filter(reading_system = rs)
#         for evaluation in evaluations:
#             print "Checking evaluation from {0} (ID = {1})".format(evaluation.last_updated, evaluation.pk)
            
#             # check that each testsuite test has a result
#             print "Checking results"
#             tests = models.Test.objects.filter(testsuite = evaluation.testsuite)
#             for test in tests:
#                 try:
#                     result = models.Result.objects.get(evaluation = evaluation, test = test)
#                 except models.Result.DoesNotExist:
#                     print "Result missing for {0}".format(test.testid)
#                     report[rs]['results'] = "Missing result record(s)"
            
#             print "Checking scores"
#             categories = models.Category.objects.filter(testsuite = evaluation.testsuite)
#             for category in categories:
#                 try:
#                     score = models.Score.objects.get(evaluation = evaluation, category = category)
#                 except models.Score.DoesNotExist:
#                     print "Score missing for {0}".format(category.name.encode('utf-8'))
#                     report[rs]['scores'] = "Missing score record(s)"

#             try:
#                 total_score = models.Score.objects.get(evaluation = evaluation, category = None)
#             except models.Score.DoesNotExist:
#                 print "Total score missing for {0}".format(rs.name)

# def repair(evalpk):
#     "repair an evaluation"
#     repair_scores(evalpk)
#     repair_results(evalpk)

# def repair_scores(evalpk):
#     "repair scores for the given evaluation"
#     try:
#         evaluation = models.Evaluation.objects.get(id=evalpk)
#     except models.Evaluation.DoesNotExist:
#         return
#     found_error = False
    
#     print "Repairing scores for {0} (evaluation ID = {1})".format(evaluation.reading_system.name, evaluation.pk)
#     categories = models.Category.objects.filter(testsuite = evaluation.testsuite)
#     for category in categories:
#         try:
#             score = models.Score.objects.get(evaluation = evaluation, category = category)
#         except models.Score.DoesNotExist:
#             found_error = True
#             print "Adding score record for {0}".format(category.name.encode('utf-8'))
#             score = models.Score(
#                 category = category,
#                 evaluation = evaluation
#             )
#             score.update(evaluation.get_category_results(category,evaluation.get_default_result_set()))
#             score.save()
#     try:
#         total_score = models.Score.objects.get(evaluation = evaluation, category = None)
#     except models.Score.DoesNotExist:
#         found_error = True
#         print "Adding total score for {0}".format(evaluation.reading_system.name)    
#         score = models.Score(
#             category = None,
#             evaluation = evaluation
#         )
#         score.update(evaluation.get_all_results(evaluation.get_default_result_set()))  
#         score.save()

#     if found_error:
#         print "Repaired scores for {0}".format(evaluation.reading_system.name)
#     else:
#         print "No errors found in scores"

# def repair_results(evalpk):
#     "repair results for the given evaluation"
#     try:
#         evaluation = models.Evaluation.objects.get(id=evalpk)
#     except models.Evaluation.DoesNotExist:
#         return
#     found_error = False
#     print "Repairing results for {0} (evaluation ID = {1})".format(evaluation.reading_system.name, evaluation.pk)
#     tests = models.Test.objects.filter(testsuite = evaluation.testsuite)
#     for test in tests:
#         try:
#             result = models.Result.objects.get(evaluation = evaluation, test = test)
#         except models.Result.DoesNotExist:
#             found_error = True
#             print "Adding result record for {0}".format(test.testid)
#             result = models.Result(test = test, evaluation = evaluation, result = common.RESULT_NOT_ANSWERED)
#             result.save()

#     if found_error:
#         print "Repaired results for {0}".format(evaluation.reading_system.name)
#     else:
#         print "No errors found in results"

def list_logged_in_users():
    # Query all non-expired sessions
    sessions = Session.objects.filter(expire_date__gte=datetime.now())
    uid_list = []

    # Build a list of user ids from that query
    for session in sessions:
        data = session.get_decoded()
        uid_list.append(data.get('_auth_user_id', None))

    users = UserProfile.objects.filter(id__in=uid_list)

    for u in users:
        print u.username

# def force_random_changes(max_changes=0, avg_distance_between=0):
#     "Pretend that a random selection of tests has changed"
#     ts = models.TestSuite.objects.get_most_recent_testsuite()
#     tests = models.Test.objects.filter(testsuite = ts)
#     if max_changes == 0:
#         max_changes = tests.count()
#     changes = 0
#     unchanged_since_last = 0
#     for t in tests:
#         if changes < max_changes and unchanged_since_last >= avg_distance_between:
#             choice = randrange(1, 4)
#             if choice == 1:
#                 print "Randomly marking {0} as new (from {1})".format(t.testid, t.source)
#                 t.flagged_as_new = True
#                 t.save()
#                 changes += 1
#                 since_last = 0
#             elif choice == 2:
#                 print "Randomly marking {0} as changed (from {1})".format(t.testid, t.source)
#                 t.flagged_as_changed == True
#                 t.save()
#                 changes += 1
#                 unchanged_since_last = 0
#             else:
#                 # don't modify the test
#                 unchanged_since_last += 1
#         else:
#             unchanged_since_last += 1
#     print "Modified {0} tests".format(changes)
#     print "updating evaluations"
#     evals = models.Evaluation.objects.filter(testsuite = ts)
#     for e in evals:
#         results = e.get_all_results(e.get_default_result_set())
#         for r in results:
#             if r.test.flagged_as_changed or r.test.flagged_as_new:
#                 r.result = None
#                 r.save()
#         e.save()

# settings.py must contain a definition for the 'previous' database in order for this to work
def copy_users():
    new_users = models.UserProfile.objects.using('previous').all()
    current_users = models.UserProfile.objects.using('default').all()
    usernames = [u.username for u in current_users]
    for u in new_users:
        if u.username not in usernames:
            print "New user found {0}".format(u.username)
            u.pk = None
            u.save(using='default')

        else:
            print "skipping duplicate {0}".format(u.username)
    print "Copied users from old database."    
    num_users = models.UserProfile.objects.using('default').all().count()
    print "Total number of users is now: {0}".format(num_users)    

def import_json(filepath):
    import import_db_for_june_refactor
    import_db_for_june_refactor.import_from_json(filepath)

def main():
    argparser = argparse.ArgumentParser(description="Collect tests")
    subparsers = argparser.add_subparsers(help='commands')
    import_parser = subparsers.add_parser('import', help='Import a testsuite into the database')
    import_parser.add_argument("source", action="store", help="Folder containing EPUBs")
    import_parser.add_argument("config", action="store", default="categories.yaml", help="categories config file")
    import_parser.set_defaults(func = lambda(args): add_testsuites(args.source, args.config))

    print_parser = subparsers.add_parser('print', help="Print (some) contents of the database")
    print_parser.set_defaults(func = lambda(args): print_testsuite())

    add_user_parser = subparsers.add_parser('add-user', help="Add a new user")
    add_user_parser.add_argument('username', action="store", help="username")
    add_user_parser.add_argument('password', action="store", help="password")
    add_user_parser.add_argument('email', action="store", help="email")
    add_user_parser.add_argument('--firstname', action="store", help="first name", default="")
    add_user_parser.add_argument('--lastname', action="store", help="last name", default="")
    add_user_parser.set_defaults(func = lambda(args): add_user(args.username, args.email, args.password, args.firstname, args.lastname))

    add_rs_parser = subparsers.add_parser('add-rs', help="Add a new reading system")
    add_rs_parser.add_argument('name', action="store", help="reading system name")
    add_rs_parser.set_defaults(func = lambda(args): add_rs(args.name))

    
    export_parser = subparsers.add_parser('export', help="Export evaluation data for all reading systems")
    export_parser.add_argument("file", action="store", help="store the xml file here")
    export_parser.set_defaults(func = lambda(args): export(args.file))

    geneval_parser = subparsers.add_parser('geneval', help="Generate random evaluation data for the given reading system")
    geneval_parser.add_argument("rs", action="store", help="reading system ID")
    geneval_parser.add_argument("type", action="store", help="DEFAULT or ACCESSIBILITY")
    geneval_parser.set_defaults(func = lambda(args): geneval(args.rs, args.type))

    listrs_parser = subparsers.add_parser('listrs', help="List all reading systems and their IDs")
    listrs_parser.set_defaults(func = lambda(args): listrs())

    emails_parser = subparsers.add_parser('emails', help="List user emails")
    emails_parser.set_defaults(func = lambda(args): getemails())

    # integrity_parser = subparsers.add_parser('integrity', help="check db integrity")
    # integrity_parser.set_defaults(func = lambda(args): integrity_check())

    # repair_scores_parser = subparsers.add_parser('repair', help="repair an evaluation")
    # repair_scores_parser.add_argument("eval", action="store", help="evaluation ID")
    # repair_scores_parser.set_defaults(func = lambda(args): repair(args.eval))

    listusers_parser = subparsers.add_parser("listusers", help="list all users")
    listusers_parser.set_defaults(func = lambda(args): listusers())

    list_logged_in_users_parser = subparsers.add_parser("list-logged-in-users", help="list logged in users")
    list_logged_in_users_parser.set_defaults(func = lambda(args): list_logged_in_users())

    # force_random_changes_parser = subparsers.add_parser("force-change-tests", help="pretend some (max 20) tests have changed")
    # force_random_changes_parser.set_defaults(func = lambda(args): force_random_changes(20, 30))

    copy_users_parser = subparsers.add_parser('copy-users', help="Copy all users")
    copy_users_parser.set_defaults(func = lambda(args): copy_users())

    import_json_parser = subparsers.add_parser('import-json', help="Import DB data from json")
    import_json_parser.add_argument("filepath", action="store", help="JSON data file")
    import_json_parser.set_defaults(func = lambda(args): import_json(args.filepath))
    
    args = argparser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
