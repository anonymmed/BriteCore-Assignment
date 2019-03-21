function PolicyViewModel(data) {
    var self = this;
    self.id = ko.observable(data.id);
    self.balance = ko.observable(data.balance);
    self.agent = ko.observable(data.agent);
    self.agent_name = ko.observable(data.agent_name);
    self.insured = ko.observable(data.insured);
    self.annual_premium = ko.observable(data.annual_premium);
    self.billing_schedule = ko.observable(data.billing_schedule);
    self.cancel_date = ko.observable(data.cancel_date);
    self.effective_date = ko.observable(data.effective_date);
    self.invoices = ko.observableArray(data.invoices);
    self.payments = ko.observableArray(data.payments);
    self.status = ko.observable(data.status);
}

function AppViewModel() {
    var self = this;
    self.policy = ko.observable(new PolicyViewModel(""));
    self.policy_id = ko.observable().extend({ required: true });
    self.policy_date = ko.observable().extend({ required: true });

    self.error_message = ko.observable("");
    self.error = ko.observable(false);

    self.search = function () {

        if (this.errors().length > 0) {
            this.errors.showAllMessages();
            return;
        }

        params = self.policy_id() + "/" + self.policy_date();
        self.error(false);

        $.ajax({
            url: '/policy/' + params,
            contentType: 'application/json',
            type: 'GET',
            cache: false,
            success: function (data) {
              if (data == '') {
                swal("Sorry!", 'Policy Not Found', 'error');
              } else {
                console.log("data : "+data);
                self.policy(new PolicyViewModel(data));
                return;
                }
            }
          });
    }
}

appViewModel = new AppViewModel();

appViewModel.errors = ko.validation.group(appViewModel);

appViewModel.requireLocation = function() {
    viewappViewModelModel.location.extend({required: true});
};

ko.applyBindings(appViewModel);
